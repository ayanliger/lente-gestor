"""
Indexador — coleta entidades do banco, renderiza, embeda e persiste em
`documentos_rag` via upsert.

Dois pontos-chave:

1. **Idempotência por hash**: antes de chamar embed, comparamos
   `(chave_unica, hash_conteudo, modelo_embedding)` com o que já existe no
   banco. Documentos inalterados são pulados → zero custo Gemini quando nada
   mudou.

2. **Upsert atômico**: `INSERT ... ON CONFLICT (chave_unica) DO UPDATE` do
   dialect PostgreSQL, num único roundtrip por lote.

A função pública é `reindexar(fontes, cliente)`. Também é chamada pelos
scripts de ingestão de negócio (auto-reindex) e pelo `scripts/ingest_rag.py`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from decimal import Decimal

import structlog
from sqlalchemy import Select, case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.contratacoes import Contrato, Fornecedor, ItemPCA
from app.models.orcamento import ExecucaoOrcamentaria, IndicadorFiscal
from app.models.rag import DocumentoRag, FonteDocumento
from app.services.rag.client import (
    GeminiClient,
    get_gemini_client,
    identificador_modelo_embedding,
)
from app.services.rag.renderizadores import (
    DocumentoRenderizado,
    LinhaResumoFuncao,
    LinhaResumoPCA,
    renderizar_contrato,
    renderizar_indicador_fiscal,
    renderizar_resumo_funcao,
    renderizar_resumo_pca,
)

logger = structlog.get_logger()

# Constantes do RREO-Anexo 02 (espelham as usadas no endpoint
# /orcamento/resumo-por-funcao para manter consistência).
_ROTULO_FUNCOES = "Total das Despesas Exceto Intra-Orçamentárias"
_COL_DOT_INICIAL = "DOTAÇÃO INICIAL"
_COL_DOT_ATUALIZADA = "DOTAÇÃO ATUALIZADA (a)"
_COL_EMPENHADO = "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)"
_COL_LIQUIDADO = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)"
_COL_SALDO = "SALDO (c) = (a-b)"


# ──────────────────────────────────────────
# Coletores (DB → lista de DocumentoRenderizado)
# ──────────────────────────────────────────


async def _coletar_contratos(db: AsyncSession) -> list[DocumentoRenderizado]:
    """Renderiza todos os contratos + fornecedor associado."""
    query: Select = select(Contrato, Fornecedor).outerjoin(
        Fornecedor, Contrato.fornecedor_id == Fornecedor.id
    )
    result = await db.execute(query)
    docs: list[DocumentoRenderizado] = []
    for contrato, fornecedor in result.all():
        docs.append(renderizar_contrato(contrato, fornecedor))
    return docs


async def _coletar_indicadores_fiscais(
    db: AsyncSession,
) -> list[DocumentoRenderizado]:
    """Renderiza todos os indicadores fiscais persistidos."""
    result = await db.execute(select(IndicadorFiscal))
    return [renderizar_indicador_fiscal(i) for i in result.scalars().all()]


async def _coletar_resumo_funcao(db: AsyncSession) -> list[DocumentoRenderizado]:
    """Pivoteia RREO-Anexo 02 por (exercicio, periodo, funcao).

    Estrutura idêntica à do endpoint `/orcamento/resumo-por-funcao`, mas
    varrendo todos os períodos disponíveis em vez de apenas o mais recente.
    """
    def pivot(col: str):
        return func.max(case((ExecucaoOrcamentaria.coluna == col, ExecucaoOrcamentaria.valor)))

    query = (
        select(
            ExecucaoOrcamentaria.exercicio.label("exercicio"),
            ExecucaoOrcamentaria.periodo.label("periodo"),
            ExecucaoOrcamentaria.conta.label("funcao"),
            pivot(_COL_DOT_INICIAL).label("dotacao_inicial"),
            pivot(_COL_DOT_ATUALIZADA).label("dotacao_atualizada"),
            pivot(_COL_EMPENHADO).label("empenhado"),
            pivot(_COL_LIQUIDADO).label("liquidado"),
            pivot(_COL_SALDO).label("saldo"),
        )
        .where(
            ExecucaoOrcamentaria.tipo_relatorio == "RREO",
            ExecucaoOrcamentaria.anexo == "RREO-Anexo 02",
            ExecucaoOrcamentaria.rotulo == _ROTULO_FUNCOES,
            ExecucaoOrcamentaria.conta.notilike("DESPESAS%"),
            ExecucaoOrcamentaria.conta != "TOTAL (III) = (I + II)",
            ExecucaoOrcamentaria.periodo.isnot(None),
        )
        .group_by(
            ExecucaoOrcamentaria.exercicio,
            ExecucaoOrcamentaria.periodo,
            ExecucaoOrcamentaria.conta,
        )
    )
    result = await db.execute(query)
    docs: list[DocumentoRenderizado] = []
    for row in result.all():
        linha = LinhaResumoFuncao(
            exercicio=row.exercicio,
            periodo=row.periodo,
            funcao=row.funcao,
            dotacao_inicial=_decimal(row.dotacao_inicial),
            dotacao_atualizada=_decimal(row.dotacao_atualizada),
            empenhado=_decimal(row.empenhado),
            liquidado=_decimal(row.liquidado),
            saldo=_decimal(row.saldo),
        )
        docs.append(renderizar_resumo_funcao(linha))
    return docs


async def _coletar_resumo_pca(db: AsyncSession) -> list[DocumentoRenderizado]:
    """Agrega `itens_pca` por (exercicio, funcao).

    `categoria` é usado como proxy de função, consistente com o schema do
    PCA no PNCP (os itens trazem categoria, não função explícita). Se
    `categoria` for nulo, o item entra em "Não classificado".
    """
    funcao_expr = func.coalesce(ItemPCA.categoria, "Não classificado").label("funcao")

    # Agrupamento principal — totais por função/exercício
    agregacao = (
        select(
            ItemPCA.ano_exercicio.label("exercicio"),
            funcao_expr,
            func.count(ItemPCA.id).label("qtd_itens"),
            func.sum(ItemPCA.valor_estimado).label("valor_estimado_total"),
            func.sum(ItemPCA.valor_executado).label("valor_executado_total"),
        )
        .group_by(ItemPCA.ano_exercicio, funcao_expr)
    )

    result = await db.execute(agregacao)
    rows = result.all()

    docs: list[DocumentoRenderizado] = []
    for row in rows:
        # Situação predominante: faz uma query secundária simples (barata com
        # índice em ano_exercicio); aceitamos n+1 porque a cardinalidade é
        # tipicamente <100 funções por exercício.
        situacao_query = (
            select(ItemPCA.situacao, func.count(ItemPCA.id))
            .where(
                ItemPCA.ano_exercicio == row.exercicio,
                func.coalesce(ItemPCA.categoria, "Não classificado") == row.funcao,
                ItemPCA.situacao.isnot(None),
            )
            .group_by(ItemPCA.situacao)
            .order_by(func.count(ItemPCA.id).desc())
            .limit(1)
        )
        situacao_result = await db.execute(situacao_query)
        predominante = situacao_result.first()
        situacao_predominante = predominante[0] if predominante else None

        linha = LinhaResumoPCA(
            exercicio=row.exercicio,
            funcao=row.funcao,
            qtd_itens=row.qtd_itens,
            valor_estimado_total=_decimal(row.valor_estimado_total),
            valor_executado_total=_decimal(row.valor_executado_total),
            situacao_predominante=situacao_predominante,
        )
        docs.append(renderizar_resumo_pca(linha))
    return docs


def _decimal(valor) -> Decimal | None:
    """Converte valores numéricos retornados pelo SQL para Decimal."""
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


# ──────────────────────────────────────────
# Orquestrador
# ──────────────────────────────────────────


_COLETORES = {
    FonteDocumento.CONTRATO: _coletar_contratos,
    FonteDocumento.INDICADOR_FISCAL: _coletar_indicadores_fiscais,
    FonteDocumento.RESUMO_FUNCAO: _coletar_resumo_funcao,
    FonteDocumento.RESUMO_PCA: _coletar_resumo_pca,
}


async def reindexar(
    fontes: Iterable[FonteDocumento] | None = None,
    *,
    lote: int = 64,
    dry_run: bool = False,
    cliente: GeminiClient | None = None,
) -> dict[str, int]:
    """Reindexa os tipos de documento solicitados.

    Args:
        fontes: subset a reindexar; `None` = todas.
        lote: tamanho do batch de embedding.
        dry_run: renderiza + loga contagens mas não embeda nem escreve.
        cliente: GeminiClient já instanciado (para reuso). Se `None`, resolve
            via factory `get_gemini_client()`.

    Returns:
        Contagens: criados, atualizados, reaproveitados, falhados, total.
    """
    fontes_alvo = list(fontes) if fontes is not None else list(_COLETORES.keys())
    stats = {"criados": 0, "atualizados": 0, "reaproveitados": 0, "falhados": 0, "total": 0}
    modelo = identificador_modelo_embedding()

    if not dry_run and cliente is None:
        cliente = get_gemini_client()

    async with async_session() as db:
        renderizados: list[DocumentoRenderizado] = []
        for fonte in fontes_alvo:
            coletor = _COLETORES[fonte]
            docs = await coletor(db)
            logger.info("rag.indexador.coletado", fonte=fonte.value, qtd=len(docs))
            renderizados.extend(docs)

        stats["total"] = len(renderizados)
        if not renderizados:
            return stats

        # Mapa de hashes existentes, para skip de re-embed.
        chaves = [d.chave_unica for d in renderizados]
        existentes_result = await db.execute(
            select(
                DocumentoRag.chave_unica,
                DocumentoRag.hash_conteudo,
                DocumentoRag.modelo_embedding,
            ).where(DocumentoRag.chave_unica.in_(chaves))
        )
        existentes = {
            row.chave_unica: (row.hash_conteudo, row.modelo_embedding)
            for row in existentes_result.all()
        }

        # Particiona em: reaproveitáveis (hash+modelo casam) vs precisam embedar.
        precisa_embedar: list[DocumentoRenderizado] = []
        for doc in renderizados:
            existente = existentes.get(doc.chave_unica)
            if existente and existente == (doc.hash_conteudo, modelo):
                stats["reaproveitados"] += 1
                continue
            precisa_embedar.append(doc)

        logger.info(
            "rag.indexador.diff",
            total=stats["total"],
            reaproveitados=stats["reaproveitados"],
            precisa_embedar=len(precisa_embedar),
        )

        if dry_run or not precisa_embedar:
            return stats

        # Embed + upsert em lotes.
        for inicio in range(0, len(precisa_embedar), lote):
            batch = precisa_embedar[inicio : inicio + lote]
            try:
                vetores = await cliente.embed_batch(  # type: ignore[union-attr]
                    [d.conteudo_texto for d in batch],
                    task_type="RETRIEVAL_DOCUMENT",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("rag.indexador.embed_falhou", erro=str(exc), qtd=len(batch))
                stats["falhados"] += len(batch)
                continue

            valores = [
                {
                    "fonte": doc.fonte.value,
                    "referencia_tipo": doc.referencia_tipo,
                    "referencia_id": doc.referencia_id,
                    "chave_unica": doc.chave_unica,
                    "titulo": doc.titulo,
                    "conteudo_texto": doc.conteudo_texto,
                    "metadados": doc.metadados,
                    "embedding": vetor,
                    "modelo_embedding": modelo,
                    "hash_conteudo": doc.hash_conteudo,
                }
                for doc, vetor in zip(batch, vetores, strict=True)
            ]

            stmt = pg_insert(DocumentoRag).values(valores)
            stmt = stmt.on_conflict_do_update(
                index_elements=[DocumentoRag.chave_unica],
                set_={
                    "fonte": stmt.excluded.fonte,
                    "referencia_tipo": stmt.excluded.referencia_tipo,
                    "referencia_id": stmt.excluded.referencia_id,
                    "titulo": stmt.excluded.titulo,
                    "conteudo_texto": stmt.excluded.conteudo_texto,
                    "metadados": stmt.excluded.metadados,
                    "embedding": stmt.excluded.embedding,
                    "modelo_embedding": stmt.excluded.modelo_embedding,
                    "hash_conteudo": stmt.excluded.hash_conteudo,
                    "indexado_em": func.now(),
                },
            )
            await db.execute(stmt)

            # Classifica criados vs atualizados consultando `existentes` pré-calculado.
            for doc in batch:
                if doc.chave_unica in existentes:
                    stats["atualizados"] += 1
                else:
                    stats["criados"] += 1

        await db.commit()

    logger.info("rag.indexador.concluido", **stats)
    return stats


# Mapeamento das fontes reindexadas por script de ingestão de negócio.
# Cada script importa essa tabela e chama `reindexar(fontes=...)` ao fim.
FONTES_POR_SCRIPT: dict[str, list[FonteDocumento]] = {
    "pncp": [FonteDocumento.CONTRATO, FonteDocumento.RESUMO_PCA],
    "orcamento": [FonteDocumento.RESUMO_FUNCAO],
    "rgf": [FonteDocumento.INDICADOR_FISCAL],
}


__all__ = [
    "reindexar",
    "FONTES_POR_SCRIPT",
    # Re-export para facilitar testes isolados do mapeamento:
    "LinhaResumoFuncao",
    "LinhaResumoPCA",
]


# Silencia linters sobre imports usados apenas em tipos via dataclass asdict
_ = asdict
