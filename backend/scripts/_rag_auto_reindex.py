"""
Utilitário compartilhado pelos scripts de ingestão de negócio para acionar
a reindexação RAG imediatamente após a persistência dos dados.

Centraliza o padrão: log consistente, tratamento de falha que não reverte
a ingestão de negócio (ver ADR 10.6 em `docs/RAG_DESIGN.md`).
"""

from __future__ import annotations

import asyncio

import structlog

from app.models.rag import FonteDocumento
from app.services.rag.indexador import reindexar

logger = structlog.get_logger()


def reindex_apos_ingestao(
    fontes: list[FonteDocumento],
    *,
    sem_reindex: bool = False,
) -> dict[str, int] | None:
    """Executa reindexação síncrona das fontes afetadas.

    Retorna `None` se `sem_reindex=True` ou se ocorrer falha (ingestão
    de negócio não é revertida).
    """
    if sem_reindex:
        logger.info("rag.auto_reindex.pulado", motivo="--sem-reindex")
        return None

    logger.info(
        "rag.auto_reindex.iniciando",
        fontes=[f.value for f in fontes],
    )
    try:
        stats = asyncio.run(reindexar(fontes=fontes))
    except Exception as exc:  # pragma: no cover
        logger.error(
            "rag.auto_reindex.falhou",
            erro=str(exc),
            fontes=[f.value for f in fontes],
            remediacao=(
                "Dados de negócio já persistiram. Rode manualmente: "
                "make ingest-rag"
            ),
        )
        return None

    logger.info("rag.auto_reindex.concluido", **stats)
    return stats
