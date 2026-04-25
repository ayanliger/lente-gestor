"""
Renderizadores: convertem entidades de domínio em documentos RAG.

Cada função é pura (sem I/O, sem DB) e devolve um `DocumentoRenderizado` com
título, conteúdo em português, metadados estruturados e a `chave_unica` usada
no upsert.

A escolha dos tipos de documento é guiada pelo valor de consulta:
- CONTRATO              → perguntas sobre um contrato específico (fornecedor, vigência)
- INDICADOR_FISCAL      → perguntas sobre LRF / mínimos constitucionais
- RESUMO_FUNCAO         → execução orçamentária por função (RREO-Anexo 02)
- RESUMO_PCA            → plano anual agregado por função (cruzamento PCA × execução)
- RESUMO_RECEITA        → receita orçamentária por categoria (RREO-Anexo 01)
- RESUMO_NATUREZA_DESPESA → despesa por GND/categoria econômica (Pessoal, Custeio,
                            Investimentos, etc. — RREO-Anexo 01)
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.contratacoes import Contrato, Fornecedor, ItemPCA
from app.models.orcamento import ExecucaoOrcamentaria, IndicadorFiscal
from app.models.rag import FonteDocumento


@dataclass(slots=True)
class DocumentoRenderizado:
    """Resultado puro de uma renderização, pronto para embedar + upsert."""

    fonte: FonteDocumento
    referencia_tipo: str
    referencia_id: uuid.UUID | None
    chave_unica: str
    titulo: str
    conteudo_texto: str
    metadados: dict[str, Any]

    @property
    def hash_conteudo(self) -> str:
        """SHA-256 do texto; base do skip de re-embed idempotente."""
        return hashlib.sha256(self.conteudo_texto.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────
# Helpers de formatação
# ──────────────────────────────────────────


def _fmt_brl(valor: Decimal | float | int | None) -> str:
    if valor is None:
        return "não informado"
    v = float(valor)
    if v >= 1_000_000_000:
        return f"R$ {v / 1_000_000_000:.2f} bi"
    if v >= 1_000_000:
        return f"R$ {v / 1_000_000:.2f} mi"
    if v >= 1_000:
        return f"R$ {v / 1_000:.1f} mil"
    return f"R$ {v:.2f}"


def _fmt_data(valor: Any) -> str:
    if valor is None:
        return "não informado"
    return str(valor)


def _fmt_pct(valor: Decimal | float | None) -> str:
    if valor is None:
        return "não informado"
    return f"{float(valor):.2f}%"


# ──────────────────────────────────────────
# CONTRATO
# ──────────────────────────────────────────


def renderizar_contrato(
    contrato: Contrato,
    fornecedor: Fornecedor | None,
) -> DocumentoRenderizado:
    """Renderiza um contrato firmado como documento indexável."""
    nome_fornecedor = fornecedor.nome if fornecedor else "fornecedor não identificado"
    cnpj_fornecedor = fornecedor.cpf_cnpj if fornecedor else "—"

    linhas = [
        f"Contrato nº {contrato.numero_contrato or contrato.pncp_id or contrato.id}",
        f"Objeto: {contrato.objeto or 'não informado'}",
        f"Fornecedor: {nome_fornecedor} (CPF/CNPJ {cnpj_fornecedor}).",
        f"Valor inicial: {_fmt_brl(contrato.valor_inicial)}.",
    ]
    if contrato.valor_atual and contrato.valor_atual != contrato.valor_inicial:
        linhas.append(f"Valor atual após aditivos: {_fmt_brl(contrato.valor_atual)}.")
    if contrato.valor_aditivos:
        linhas.append(f"Total de aditivos: {_fmt_brl(contrato.valor_aditivos)}.")
    linhas.append(
        f"Vigência: {_fmt_data(contrato.data_inicio_vigencia)} a "
        f"{_fmt_data(contrato.data_fim_vigencia)}."
    )
    if contrato.situacao:
        linhas.append(f"Situação: {contrato.situacao}.")
    if contrato.categoria:
        cat = contrato.categoria
        if contrato.subcategoria:
            cat = f"{cat} / {contrato.subcategoria}"
        linhas.append(f"Categoria: {cat}.")
    if contrato.data_assinatura:
        linhas.append(f"Assinado em {_fmt_data(contrato.data_assinatura)}.")

    conteudo = "\n".join(linhas)

    metadados: dict[str, Any] = {
        "numero_contrato": contrato.numero_contrato,
        "pncp_id": contrato.pncp_id,
        "fornecedor_nome": nome_fornecedor,
        "fornecedor_cnpj": cnpj_fornecedor,
        "valor_inicial": (
            float(contrato.valor_inicial) if contrato.valor_inicial else None
        ),
        "valor_atual": (
            float(contrato.valor_atual) if contrato.valor_atual else None
        ),
        "data_inicio_vigencia": (
            str(contrato.data_inicio_vigencia)
            if contrato.data_inicio_vigencia
            else None
        ),
        "data_fim_vigencia": (
            str(contrato.data_fim_vigencia)
            if contrato.data_fim_vigencia
            else None
        ),
        "situacao": contrato.situacao,
        "categoria": contrato.categoria,
    }

    titulo_objeto = (contrato.objeto or "Contrato").strip()
    if len(titulo_objeto) > 180:
        titulo_objeto = titulo_objeto[:177] + "..."
    titulo = f"Contrato — {titulo_objeto}"

    return DocumentoRenderizado(
        fonte=FonteDocumento.CONTRATO,
        referencia_tipo="contrato",
        referencia_id=contrato.id,
        chave_unica=f"contrato:{contrato.id}",
        titulo=titulo[:500],
        conteudo_texto=conteudo,
        metadados=metadados,
    )


# ──────────────────────────────────────────
# INDICADOR_FISCAL
# ──────────────────────────────────────────


_DESCRICAO_SITUACAO = {
    "OK": "dentro dos limites legais",
    "ALERTA": "em alerta, próximo do limite (≥ 90%)",
    "EXCEDIDO": "ACIMA do limite legal",
    "ABAIXO_MINIMO": "ABAIXO do mínimo constitucional",
    "SEM_DADO": "sem dado disponível para o período",
}


def renderizar_indicador_fiscal(
    indicador: IndicadorFiscal,
) -> DocumentoRenderizado:
    """Renderiza um indicador LRF/mínimo constitucional como narrativa."""
    situacao_legivel = _DESCRICAO_SITUACAO.get(indicador.situacao, indicador.situacao)

    linhas = [
        f"Indicador: {indicador.descricao} (código {indicador.codigo}).",
        f"Exercício {indicador.exercicio}"
        + (f", período {indicador.periodo}." if indicador.periodo else "."),
        f"Valor apurado: {_fmt_pct(indicador.valor)}.",
        f"Limite legal: {_fmt_pct(indicador.limite_legal)}.",
        f"Situação: {indicador.situacao} — {situacao_legivel}.",
        f"Fonte: {indicador.fonte_relatorio}"
        + (f" {indicador.fonte_exercicio}" if indicador.fonte_exercicio else "")
        + (f"/P{indicador.fonte_periodo}" if indicador.fonte_periodo else "")
        + ".",
    ]

    conteudo = "\n".join(linhas)

    metadados: dict[str, Any] = {
        "codigo": indicador.codigo,
        "exercicio": indicador.exercicio,
        "periodo": indicador.periodo,
        "valor": float(indicador.valor) if indicador.valor is not None else None,
        "limite_legal": (
            float(indicador.limite_legal)
            if indicador.limite_legal is not None
            else None
        ),
        "situacao": indicador.situacao,
        "fonte_relatorio": indicador.fonte_relatorio,
    }

    return DocumentoRenderizado(
        fonte=FonteDocumento.INDICADOR_FISCAL,
        referencia_tipo="indicador_fiscal",
        referencia_id=indicador.id,
        chave_unica=f"indicador:{indicador.id}",
        titulo=f"Indicador fiscal — {indicador.descricao}"[:500],
        conteudo_texto=conteudo,
        metadados=metadados,
    )


# ──────────────────────────────────────────
# RESUMO_FUNCAO
# ──────────────────────────────────────────


@dataclass(slots=True)
class LinhaResumoFuncao:
    """Linha agregada por (exercicio, periodo, função) a partir do RREO-Anexo 02."""

    exercicio: int
    periodo: int
    funcao: str
    dotacao_inicial: Decimal | None
    dotacao_atualizada: Decimal | None
    empenhado: Decimal | None
    liquidado: Decimal | None
    saldo: Decimal | None


def renderizar_resumo_funcao(linha: LinhaResumoFuncao) -> DocumentoRenderizado:
    """Renderiza a execução orçamentária de uma função num bimestre."""
    pct_exec: float | None = None
    if linha.dotacao_atualizada and linha.empenhado is not None:
        dot = float(linha.dotacao_atualizada)
        if dot > 0:
            pct_exec = (float(linha.empenhado) / dot) * 100

    linhas = [
        f"Execução orçamentária — função {linha.funcao} no exercício "
        f"{linha.exercicio}, bimestre {linha.periodo}.",
        f"Dotação inicial: {_fmt_brl(linha.dotacao_inicial)}.",
        f"Dotação atualizada: {_fmt_brl(linha.dotacao_atualizada)}.",
        f"Empenhado até o bimestre: {_fmt_brl(linha.empenhado)}.",
        f"Liquidado até o bimestre: {_fmt_brl(linha.liquidado)}.",
        f"Saldo a executar: {_fmt_brl(linha.saldo)}.",
    ]
    if pct_exec is not None:
        linhas.append(f"Percentual de execução: {pct_exec:.1f}%.")

    conteudo = "\n".join(linhas)

    metadados: dict[str, Any] = {
        "exercicio": linha.exercicio,
        "periodo": linha.periodo,
        "funcao": linha.funcao,
        "dotacao_inicial": float(linha.dotacao_inicial) if linha.dotacao_inicial else None,
        "dotacao_atualizada": float(linha.dotacao_atualizada) if linha.dotacao_atualizada else None,
        "empenhado": float(linha.empenhado) if linha.empenhado else None,
        "liquidado": float(linha.liquidado) if linha.liquidado else None,
        "saldo": float(linha.saldo) if linha.saldo else None,
        "pct_execucao": pct_exec,
    }

    chave = f"resumo_funcao:{linha.exercicio}:{linha.periodo}:{linha.funcao}"
    titulo = f"Execução {linha.funcao} — {linha.exercicio}/B{linha.periodo}"

    return DocumentoRenderizado(
        fonte=FonteDocumento.RESUMO_FUNCAO,
        referencia_tipo="resumo_funcao",
        referencia_id=None,  # documento agregado, sem registro único
        chave_unica=chave,
        titulo=titulo[:500],
        conteudo_texto=conteudo,
        metadados=metadados,
    )


# ──────────────────────────────────────────
# RESUMO_PCA
# ──────────────────────────────────────────


@dataclass(slots=True)
class LinhaResumoPCA:
    """Agregado de `itens_pca` por (exercício, função)."""

    exercicio: int
    funcao: str
    qtd_itens: int
    valor_estimado_total: Decimal | None
    valor_executado_total: Decimal | None
    situacao_predominante: str | None


def renderizar_resumo_pca(linha: LinhaResumoPCA) -> DocumentoRenderizado:
    """Renderiza o plano anual (PCA) agregado por função.

    Elemento-chave para cruzar planejamento x execução no eixo `(exercicio,
    função)` — mesma granularidade do `RESUMO_FUNCAO`.
    """
    pct_exec: float | None = None
    if linha.valor_estimado_total and linha.valor_executado_total is not None:
        est = float(linha.valor_estimado_total)
        if est > 0:
            pct_exec = (float(linha.valor_executado_total) / est) * 100

    linhas = [
        f"Plano Anual de Contratações (PCA) — função {linha.funcao} no "
        f"exercício {linha.exercicio}.",
        f"Itens planejados: {linha.qtd_itens}.",
        f"Valor estimado total: {_fmt_brl(linha.valor_estimado_total)}.",
        f"Valor executado até o momento: {_fmt_brl(linha.valor_executado_total)}.",
    ]
    if pct_exec is not None:
        linhas.append(f"Percentual executado vs planejado: {pct_exec:.1f}%.")
    if linha.situacao_predominante:
        linhas.append(f"Situação predominante dos itens: {linha.situacao_predominante}.")

    conteudo = "\n".join(linhas)

    metadados: dict[str, Any] = {
        "exercicio": linha.exercicio,
        "funcao": linha.funcao,
        "qtd_itens": linha.qtd_itens,
        "valor_estimado_total": (
            float(linha.valor_estimado_total)
            if linha.valor_estimado_total
            else None
        ),
        "valor_executado_total": (
            float(linha.valor_executado_total)
            if linha.valor_executado_total
            else None
        ),
        "pct_execucao": pct_exec,
        "situacao_predominante": linha.situacao_predominante,
    }

    chave = f"resumo_pca:{linha.exercicio}:{linha.funcao}"
    titulo = f"PCA {linha.funcao} — {linha.exercicio}"

    return DocumentoRenderizado(
        fonte=FonteDocumento.RESUMO_PCA,
        referencia_tipo="resumo_pca",
        referencia_id=None,
        chave_unica=chave,
        titulo=titulo[:500],
        conteudo_texto=conteudo,
        metadados=metadados,
    )


# ────────────────────────────────────────
# RESUMO_RECEITA
# ────────────────────────────────────────


@dataclass(slots=True)
class LinhaResumoReceita:
    """Agregado de receita por (exercício, bimestre, categoria) do RREO-Anexo 01.

    Cada linha cobre uma rubrica de receita (Tributária, Patrimonial,
    Transferências, etc.) ou um total (Correntes / Capital / Geral).
    `categoria_codigo` é o `cod_conta` original do SICONFI; `categoria_legivel`
    é a forma humana usada no título e no texto indexado.
    """

    exercicio: int
    periodo: int
    categoria_codigo: str
    categoria_legivel: str
    previsao_inicial: Decimal | None
    previsao_atualizada: Decimal | None
    arrecadado_no_bimestre: Decimal | None
    arrecadado_ate_bimestre: Decimal | None
    saldo: Decimal | None


def renderizar_resumo_receita(linha: LinhaResumoReceita) -> DocumentoRenderizado:
    """Renderiza receita orçamentária de uma rubrica num bimestre."""
    pct_arrecadacao: float | None = None
    if linha.previsao_atualizada and linha.arrecadado_ate_bimestre is not None:
        prev = float(linha.previsao_atualizada)
        if prev > 0:
            pct_arrecadacao = (
                float(linha.arrecadado_ate_bimestre) / prev
            ) * 100

    linhas = [
        f"Receita orçamentária — {linha.categoria_legivel} no exercício "
        f"{linha.exercicio}, bimestre {linha.periodo}.",
        f"Previsão inicial: {_fmt_brl(linha.previsao_inicial)}.",
        f"Previsão atualizada: {_fmt_brl(linha.previsao_atualizada)}.",
        f"Arrecadado no bimestre: {_fmt_brl(linha.arrecadado_no_bimestre)}.",
        f"Arrecadado até o bimestre: {_fmt_brl(linha.arrecadado_ate_bimestre)}.",
        f"Saldo a arrecadar: {_fmt_brl(linha.saldo)}.",
    ]
    if pct_arrecadacao is not None:
        linhas.append(
            f"Percentual de realização da previsão: {pct_arrecadacao:.1f}%."
        )

    conteudo = "\n".join(linhas)

    metadados: dict[str, Any] = {
        "exercicio": linha.exercicio,
        "periodo": linha.periodo,
        "categoria_codigo": linha.categoria_codigo,
        "categoria_legivel": linha.categoria_legivel,
        "previsao_inicial": (
            float(linha.previsao_inicial) if linha.previsao_inicial else None
        ),
        "previsao_atualizada": (
            float(linha.previsao_atualizada) if linha.previsao_atualizada else None
        ),
        "arrecadado_no_bimestre": (
            float(linha.arrecadado_no_bimestre)
            if linha.arrecadado_no_bimestre
            else None
        ),
        "arrecadado_ate_bimestre": (
            float(linha.arrecadado_ate_bimestre)
            if linha.arrecadado_ate_bimestre
            else None
        ),
        "saldo": float(linha.saldo) if linha.saldo else None,
        "pct_arrecadacao": pct_arrecadacao,
    }

    chave = (
        f"resumo_receita:{linha.exercicio}:{linha.periodo}:"
        f"{linha.categoria_codigo}"
    )
    titulo = (
        f"Receita {linha.categoria_legivel} — "
        f"{linha.exercicio}/B{linha.periodo}"
    )

    return DocumentoRenderizado(
        fonte=FonteDocumento.RESUMO_RECEITA,
        referencia_tipo="resumo_receita",
        referencia_id=None,
        chave_unica=chave,
        titulo=titulo[:500],
        conteudo_texto=conteudo,
        metadados=metadados,
    )


# ────────────────────────────────────────
# RESUMO_NATUREZA_DESPESA
# ────────────────────────────────────────


@dataclass(slots=True)
class LinhaResumoNaturezaDespesa:
    """Agregado de despesa por (exercício, bimestre, GND) do RREO-Anexo 01.

    Os GNDs principais são: Pessoal e Encargos, Juros e Encargos da Dívida,
    Outras Despesas Correntes (custeio), Investimentos (CAPEX), Inversões
    Financeiras e Amortização da Dívida; além dos totais por categoria
    econômica (Despesas Correntes e Despesas de Capital).
    """

    exercicio: int
    periodo: int
    natureza_codigo: str
    natureza_legivel: str
    dotacao_inicial: Decimal | None
    dotacao_atualizada: Decimal | None
    empenhado: Decimal | None
    liquidado: Decimal | None
    saldo: Decimal | None


def renderizar_resumo_natureza_despesa(
    linha: LinhaResumoNaturezaDespesa,
) -> DocumentoRenderizado:
    """Renderiza despesa orçamentária de um GND num bimestre."""
    pct_exec: float | None = None
    if linha.dotacao_atualizada and linha.empenhado is not None:
        dot = float(linha.dotacao_atualizada)
        if dot > 0:
            pct_exec = (float(linha.empenhado) / dot) * 100

    linhas = [
        f"Despesa orçamentária por natureza — {linha.natureza_legivel} "
        f"no exercício {linha.exercicio}, bimestre {linha.periodo}.",
        f"Dotação inicial: {_fmt_brl(linha.dotacao_inicial)}.",
        f"Dotação atualizada: {_fmt_brl(linha.dotacao_atualizada)}.",
        f"Empenhado até o bimestre: {_fmt_brl(linha.empenhado)}.",
        f"Liquidado até o bimestre: {_fmt_brl(linha.liquidado)}.",
        f"Saldo a executar: {_fmt_brl(linha.saldo)}.",
    ]
    if pct_exec is not None:
        linhas.append(f"Percentual de execução: {pct_exec:.1f}%.")

    conteudo = "\n".join(linhas)

    metadados: dict[str, Any] = {
        "exercicio": linha.exercicio,
        "periodo": linha.periodo,
        "natureza_codigo": linha.natureza_codigo,
        "natureza_legivel": linha.natureza_legivel,
        "dotacao_inicial": (
            float(linha.dotacao_inicial) if linha.dotacao_inicial else None
        ),
        "dotacao_atualizada": (
            float(linha.dotacao_atualizada) if linha.dotacao_atualizada else None
        ),
        "empenhado": float(linha.empenhado) if linha.empenhado else None,
        "liquidado": float(linha.liquidado) if linha.liquidado else None,
        "saldo": float(linha.saldo) if linha.saldo else None,
        "pct_execucao": pct_exec,
    }

    chave = (
        f"resumo_natureza:{linha.exercicio}:{linha.periodo}:"
        f"{linha.natureza_codigo}"
    )
    titulo = (
        f"Despesa {linha.natureza_legivel} — "
        f"{linha.exercicio}/B{linha.periodo}"
    )

    return DocumentoRenderizado(
        fonte=FonteDocumento.RESUMO_NATUREZA_DESPESA,
        referencia_tipo="resumo_natureza_despesa",
        referencia_id=None,
        chave_unica=chave,
        titulo=titulo[:500],
        conteudo_texto=conteudo,
        metadados=metadados,
    )


__all__ = [
    "DocumentoRenderizado",
    "LinhaResumoFuncao",
    "LinhaResumoNaturezaDespesa",
    "LinhaResumoPCA",
    "LinhaResumoReceita",
    "renderizar_contrato",
    "renderizar_indicador_fiscal",
    "renderizar_resumo_funcao",
    "renderizar_resumo_natureza_despesa",
    "renderizar_resumo_pca",
    "renderizar_resumo_receita",
]


# Dummy references to keep imports used when modules only use typing; silences
# linters that flag unused imports (ExecucaoOrcamentaria, ItemPCA are used by
# the aggregator in indexador.py but exported here too for convenience).
_ = (ExecucaoOrcamentaria, ItemPCA)
