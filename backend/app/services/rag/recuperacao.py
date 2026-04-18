"""
Recuperação — converte pergunta em embedding e busca os top-K documentos
mais similares via distância cosseno do pgvector (`<=>`).

A similaridade cosseno é `1 - distance`. Usamos essa conversão para que
números próximos de 1 signifiquem "mais relevante" (consistente com a
intuição humana).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.rag import DocumentoRag, FonteDocumento
from app.services.rag.client import GeminiClient

logger = structlog.get_logger()


@dataclass(slots=True)
class DocumentoRelevante:
    """Resultado de uma busca vetorial: documento + score cosseno."""

    doc_id: uuid.UUID
    fonte: str
    referencia_tipo: str
    referencia_id: uuid.UUID | None
    chave_unica: str
    titulo: str
    conteudo_texto: str
    metadados: dict[str, Any]
    score: float  # similaridade cosseno ∈ [0, 1]


async def buscar(
    pergunta: str,
    *,
    db: AsyncSession,
    cliente: GeminiClient,
    k: int = 6,
    fontes: Iterable[FonteDocumento] | None = None,
    limiar: float | None = None,
) -> list[DocumentoRelevante]:
    """Busca top-K documentos mais similares à pergunta.

    Args:
        pergunta: texto da pergunta em linguagem natural.
        db: sessão ativa (a rota já tem uma via DI).
        cliente: GeminiClient para gerar o embedding da pergunta.
        k: top-K candidatos a trazer antes do filtro de limiar.
        fontes: filtro opcional por tipo de documento.
        limiar: similaridade mínima ∈ [0,1]. `None` → usa
            `settings.rag_limiar_similaridade`. Documentos com score menor
            são descartados para reduzir ruído no prompt.
    """
    settings = get_settings()
    limiar_efetivo = settings.rag_limiar_similaridade if limiar is None else limiar

    vetor = await cliente.embed_text(pergunta, task_type="RETRIEVAL_QUERY")

    # `<=>` devolve distância cosseno ∈ [0,2]; para similaridade usamos 1-dist
    # (clampeada depois). Selecionamos também a distância para logging.
    dist_expr = DocumentoRag.embedding.cosine_distance(vetor).label("distancia")

    query = select(DocumentoRag, dist_expr).order_by(dist_expr.asc()).limit(k)
    if fontes is not None:
        valores = [f.value for f in fontes]
        query = query.where(DocumentoRag.fonte.in_(valores))

    result = await db.execute(query)
    rows = result.all()

    relevantes: list[DocumentoRelevante] = []
    for doc, distancia in rows:
        score = max(0.0, 1.0 - float(distancia))
        if score < limiar_efetivo:
            continue
        relevantes.append(
            DocumentoRelevante(
                doc_id=doc.id,
                fonte=doc.fonte,
                referencia_tipo=doc.referencia_tipo,
                referencia_id=doc.referencia_id,
                chave_unica=doc.chave_unica,
                titulo=doc.titulo,
                conteudo_texto=doc.conteudo_texto,
                metadados=dict(doc.metadados or {}),
                score=score,
            )
        )

    logger.info(
        "rag.recuperacao",
        k=k,
        qtd_total=len(rows),
        qtd_apos_limiar=len(relevantes),
        limiar=limiar_efetivo,
    )
    return relevantes


__all__ = ["DocumentoRelevante", "buscar"]
