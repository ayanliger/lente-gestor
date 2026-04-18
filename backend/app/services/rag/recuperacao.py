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
    fallback_minimo: int | None = None,
) -> list[DocumentoRelevante]:
    """Busca top-K documentos mais similares à pergunta.

    Política de limiar:
    - Documentos com `score >= limiar` entram naturalmente.
    - Se menos de `fallback_minimo` docs passarem, completa com os
      melhores disponíveis (mesmo abaixo do limiar). Isso evita mandar
      prompt vazio em perguntas muito amplas, onde scores tendem a ser
      baixos. O modelo decide se usa, ignora ou recusa — não o pre-filtro.

    Args:
        pergunta: texto em linguagem natural.
        db, cliente: sessão + client Gemini injetados pela rota.
        k: total de candidatos a trazer do banco antes do filtro.
        fontes: filtro opcional por tipo de documento.
        limiar: similaridade mínima ∈ [0,1]. `None` = usa settings.
        fallback_minimo: mínimo de docs a retornar mesmo sob limiar.
            `None` = usa settings.
    """
    settings = get_settings()
    limiar_efetivo = (
        settings.rag_limiar_similaridade if limiar is None else limiar
    )
    fallback = (
        settings.rag_fallback_minimo
        if fallback_minimo is None
        else fallback_minimo
    )

    vetor = await cliente.embed_text(pergunta, task_type="RETRIEVAL_QUERY")

    # `<=>` devolve distância cosseno ∈ [0,2]; similaridade = 1 - distance.
    dist_expr = DocumentoRag.embedding.cosine_distance(vetor).label("distancia")

    query = select(DocumentoRag, dist_expr).order_by(dist_expr.asc()).limit(k)
    if fontes is not None:
        valores = [f.value for f in fontes]
        query = query.where(DocumentoRag.fonte.in_(valores))

    result = await db.execute(query)
    rows = result.all()

    # Converte todas as linhas em DocumentoRelevante, ordenadas por score desc.
    todos: list[DocumentoRelevante] = []
    for doc, distancia in rows:
        score = max(0.0, 1.0 - float(distancia))
        todos.append(
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

    acima_do_limiar = [d for d in todos if d.score >= limiar_efetivo]
    if len(acima_do_limiar) >= fallback:
        relevantes = acima_do_limiar
    else:
        # Garante o piso mínimo usando os melhores disponíveis no total.
        relevantes = todos[:fallback]

    logger.info(
        "rag.recuperacao",
        k=k,
        qtd_total=len(todos),
        qtd_acima_limiar=len(acima_do_limiar),
        qtd_retornados=len(relevantes),
        limiar=limiar_efetivo,
        fallback_minimo=fallback,
        usou_fallback=len(acima_do_limiar) < fallback and len(todos) > 0,
    )
    return relevantes


__all__ = ["DocumentoRelevante", "buscar"]
