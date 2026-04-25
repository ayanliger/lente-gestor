"""Documentos estruturados para rankings orçamentários."""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orcamento import ExecucaoOrcamentaria
from app.services.orcamento_funcoes import FUNCOES_GOVERNO
from app.services.rag.recuperacao import DocumentoRelevante

_COL_FUNCAO_DOTACAO = "DOTAÇÃO ATUALIZADA (a)"
_COL_FUNCAO_EMPENHADO = "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)"
_COL_FUNCAO_LIQUIDADO = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)"
_COL_NATUREZA_DOTACAO = "DOTAÇÃO ATUALIZADA (e)"
_COL_NATUREZA_EMPENHADO = "DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)"
_COL_NATUREZA_LIQUIDADO = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)"
_ROTULO_FUNCOES = "Total das Despesas Exceto Intra-Orçamentárias"

_NATUREZAS_GRUPO = (
    "PessoalEEncargosSociais",
    "JurosEEncargosDaDivida",
    "OutrasDespesasCorrentes",
    "Investimentos",
    "Inversoes",
    "AmortizacaoDaDivida",
)

_RE_ANO = re.compile(r"\b(20\d{2})\b")
_RE_CHAVE_RANKING = re.compile(r"^ranking:despesas:(20\d{2}):B([1-6])$")
_RE_BIMESTRE = re.compile(
    r"\b(?:b|bimestre|periodo)\s*([1-6])\b|"
    r"\b([1-6])(?:o|º)?\s*bimestre\b"
)


def pergunta_pede_ranking_despesas(pergunta: str) -> bool:
    """Detecta perguntas que pedem maiores gastos/despesas."""
    normalizada = _normalizar(pergunta)
    tem_ranking = any(
        termo in normalizada
        for termo in ("maior", "maiores", "principal", "principais", "ranking", "top")
    )
    tem_despesa = any(
        termo in normalizada
        for termo in ("gasto", "gastos", "despesa", "despesas")
    )
    return tem_ranking and tem_despesa


async def gerar_documento_ranking_despesas(
    db: AsyncSession,
    pergunta: str,
    chaves_referencia: list[str] | None = None,
) -> DocumentoRelevante | None:
    """Gera ranking SQL por função e por natureza para a pergunta."""
    ano_ref, periodo_ref = _extrair_referencia_chaves(chaves_referencia or [])
    ano = _extrair_ano(pergunta) or ano_ref or await _ano_mais_recente(db)
    if ano is None:
        return None

    periodo = _extrair_periodo(pergunta)
    if periodo is None and ano_ref == ano:
        periodo = periodo_ref
    if periodo is None:
        periodo = await _periodo_mais_recente(db, ano)
    if periodo is None:
        return None

    funcoes = await _ranking_funcoes(db, ano, periodo)
    naturezas = await _ranking_naturezas(db, ano, periodo)
    if not funcoes and not naturezas:
        return None

    top_funcoes = funcoes[:10]
    top_naturezas = naturezas[:8]
    total_funcoes = sum(float(row.empenhado or 0) for row in funcoes)
    total_naturezas = sum(float(row.empenhado or 0) for row in naturezas)

    linhas = [
        f"Ranking estruturado de despesas do exercício {ano}, bimestre B{periodo}.",
        (
            "Se a pergunta não especificou bimestre, foi usado o período mais "
            "recente disponível para o exercício."
        ),
        (
            "O dashboard de composição da despesa usa a classificação por "
            "função de governo. Subfunções são outro nível analítico e não "
            "devem ser somadas junto com funções, para evitar dupla contagem."
        ),
        (
            "Maiores despesas por função de governo (RREO-Anexo 02, funções "
            "oficiais):"
        ),
        *[
            _linha_ranking(i, row.nome, row.empenhado, row.liquidado, row.dotacao)
            for i, row in enumerate(top_funcoes, start=1)
        ],
        f"Total empenhado nas funções oficiais: {_fmt_brl(total_funcoes)}.",
        (
            "Maiores grupos por natureza da despesa (RREO-Anexo 01, sem os "
            "totalizadores Despesas Correntes e Despesas de Capital):"
        ),
        *[
            _linha_ranking(i, row.nome, row.empenhado, row.liquidado, row.dotacao)
            for i, row in enumerate(top_naturezas, start=1)
        ],
        f"Total empenhado nesses grupos de natureza: {_fmt_brl(total_naturezas)}.",
        (
            "Interpretação: para 'maiores gastos/despesas' sem eixo explícito, "
            "responda primeiro por função de governo e diferencie, quando "
            "útil, do ranking por natureza econômica. Função e natureza são "
            "classificações diferentes e não devem ser comparadas como se "
            "fossem categorias excludentes."
        ),
    ]

    chave = f"ranking:despesas:{ano}:B{periodo}"
    metadados: dict[str, Any] = {
        "exercicio": ano,
        "periodo": periodo,
        "eixo_principal": "funcao_governo",
        "total_funcoes_empenhado": total_funcoes,
        "total_naturezas_empenhado": total_naturezas,
        "funcoes": [_serializar_row(row) for row in top_funcoes],
        "naturezas": [_serializar_row(row) for row in top_naturezas],
    }

    return DocumentoRelevante(
        doc_id=uuid.uuid5(uuid.NAMESPACE_URL, f"lente-gestor:{chave}"),
        fonte="RANKING_DESPESA",
        referencia_tipo="ranking_despesa",
        referencia_id=None,
        chave_unica=chave,
        titulo=f"Ranking estruturado de despesas — {ano}/B{periodo}",
        conteudo_texto="\n".join(linhas),
        metadados=metadados,
        score=1.0,
    )


def _pivot_col(nome_col: str):
    return func.max(
        case((ExecucaoOrcamentaria.coluna == nome_col, ExecucaoOrcamentaria.valor))
    )


async def _ano_mais_recente(db: AsyncSession) -> int | None:
    result = await db.execute(
        select(func.max(ExecucaoOrcamentaria.exercicio)).where(
            ExecucaoOrcamentaria.tipo_relatorio == "RREO",
            ExecucaoOrcamentaria.anexo == "RREO-Anexo 02",
        )
    )
    ano = result.scalar_one_or_none()
    return int(ano) if ano is not None else None


async def _periodo_mais_recente(db: AsyncSession, ano: int) -> int | None:
    result = await db.execute(
        select(func.max(ExecucaoOrcamentaria.periodo)).where(
            ExecucaoOrcamentaria.exercicio == ano,
            ExecucaoOrcamentaria.tipo_relatorio == "RREO",
            ExecucaoOrcamentaria.anexo == "RREO-Anexo 02",
        )
    )
    periodo = result.scalar_one_or_none()
    return int(periodo) if periodo is not None else None


async def _ranking_funcoes(db: AsyncSession, ano: int, periodo: int):
    empenhado = _pivot_col(_COL_FUNCAO_EMPENHADO)
    query = (
        select(
            ExecucaoOrcamentaria.conta.label("nome"),
            _pivot_col(_COL_FUNCAO_DOTACAO).label("dotacao"),
            empenhado.label("empenhado"),
            _pivot_col(_COL_FUNCAO_LIQUIDADO).label("liquidado"),
        )
        .where(
            ExecucaoOrcamentaria.exercicio == ano,
            ExecucaoOrcamentaria.periodo == periodo,
            ExecucaoOrcamentaria.tipo_relatorio == "RREO",
            ExecucaoOrcamentaria.anexo == "RREO-Anexo 02",
            ExecucaoOrcamentaria.rotulo == _ROTULO_FUNCOES,
            ExecucaoOrcamentaria.conta.in_(FUNCOES_GOVERNO),
        )
        .group_by(ExecucaoOrcamentaria.conta)
        .order_by(empenhado.desc().nullslast())
    )
    return (await db.execute(query)).all()


async def _ranking_naturezas(db: AsyncSession, ano: int, periodo: int):
    empenhado = _pivot_col(_COL_NATUREZA_EMPENHADO)
    query = (
        select(
            ExecucaoOrcamentaria.conta.label("nome"),
            _pivot_col(_COL_NATUREZA_DOTACAO).label("dotacao"),
            empenhado.label("empenhado"),
            _pivot_col(_COL_NATUREZA_LIQUIDADO).label("liquidado"),
        )
        .where(
            ExecucaoOrcamentaria.exercicio == ano,
            ExecucaoOrcamentaria.periodo == periodo,
            ExecucaoOrcamentaria.tipo_relatorio == "RREO",
            ExecucaoOrcamentaria.anexo == "RREO-Anexo 01",
            ExecucaoOrcamentaria.cod_conta.in_(_NATUREZAS_GRUPO),
        )
        .group_by(ExecucaoOrcamentaria.cod_conta, ExecucaoOrcamentaria.conta)
        .order_by(empenhado.desc().nullslast())
    )
    return (await db.execute(query)).all()


def _linha_ranking(
    indice: int,
    nome: str,
    empenhado: float | None,
    liquidado: float | None,
    dotacao: float | None,
) -> str:
    return (
        f"{indice}. {nome}: empenhado {_fmt_brl(empenhado)}, "
        f"liquidado {_fmt_brl(liquidado)}, dotação atualizada {_fmt_brl(dotacao)}."
    )


def _serializar_row(row) -> dict[str, Any]:
    return {
        "nome": row.nome,
        "dotacao": float(row.dotacao) if row.dotacao is not None else None,
        "empenhado": float(row.empenhado) if row.empenhado is not None else None,
        "liquidado": float(row.liquidado) if row.liquidado is not None else None,
    }


def _fmt_brl(valor: float | None) -> str:
    if valor is None:
        return "não informado"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _extrair_ano(pergunta: str) -> int | None:
    match = _RE_ANO.search(pergunta)
    return int(match.group(1)) if match else None


def _extrair_periodo(pergunta: str) -> int | None:
    match = _RE_BIMESTRE.search(_normalizar(pergunta))
    if not match:
        return None
    valor = match.group(1) or match.group(2)
    return int(valor)


def _extrair_referencia_chaves(chaves: list[str]) -> tuple[int | None, int | None]:
    for chave in reversed(chaves):
        match = _RE_CHAVE_RANKING.match(chave)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def _normalizar(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acentos if not unicodedata.combining(c)).lower()


__all__ = [
    "gerar_documento_ranking_despesas",
    "pergunta_pede_ranking_despesas",
]
