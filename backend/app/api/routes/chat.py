"""
Rota do assistente conversacional (RAG).

Uma única rota `POST /chat`:
- valida a pergunta (`min_length=3, max_length=500` via Pydantic)
- aplica rate limit de cortesia (`slowapi`) conforme `settings.rate_limit_chat`
- chama o gerador RAG
- emite um evento `structlog` rico (`chat.request`) com pergunta, docs,
  citações, latência por leg e uso de tokens — base natural do golden set
  evolutivo

O endpoint é stateless: sem histórico/sessão/autenticação no MVP.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import ChatRequest, ChatResponse, FonteCitadaOut
from app.config import get_settings
from app.services.rag.client import GeminiClient, get_gemini_client
from app.services.rag.gerador import responder

logger = structlog.get_logger()

router = APIRouter(prefix="/chat", tags=["Chat / RAG"])

# Limiter global exportado para o app registrar o handler de 429.
# `get_remote_address` usa o IP da conexão (X-Forwarded-For quando configurado).
limiter = Limiter(key_func=get_remote_address)


def _cliente_gemini() -> GeminiClient:
    """Dependency FastAPI — instancia o cliente cacheado via factory."""
    return get_gemini_client()


@router.post("/", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().rate_limit_chat)
async def chat(
    request: Request,  # exigido pelo slowapi para detectar o IP
    payload: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    cliente: Annotated[GeminiClient, Depends(_cliente_gemini)],
) -> ChatResponse:
    """Responde uma pergunta com citações ou recusa explícita.

    Toda chamada gera um evento `chat.request` no log estruturado com:
    pergunta, docs recuperados + scores, resposta, citações extraídas,
    recusou, latências (embed/busca/gen/total) e uso de tokens.
    """
    request_id = str(uuid.uuid4())

    resposta = await responder(
        payload.pergunta,
        db=db,
        cliente=cliente,
    )

    fontes_out = [
        FonteCitadaOut(
            indice=f.indice,
            doc_id=f.doc_id,
            fonte=f.fonte,
            referencia_tipo=f.referencia_tipo,
            referencia_id=f.referencia_id,
            chave_unica=f.chave_unica,
            titulo=f.titulo,
            metadados=f.metadados,
            score=f.score,
        )
        for f in resposta.fontes
    ]

    logger.info(
        "chat.request",
        request_id=request_id,
        pergunta=payload.pergunta,
        docs_recuperados=[
            {
                "doc_id": str(d.doc_id),
                "chave_unica": d.chave_unica,
                "fonte": d.fonte,
                "score": round(d.score, 4),
            }
            for d in resposta.docs_recuperados
        ],
        docs_usados=len(resposta.docs_recuperados),
        resposta_texto=resposta.texto,
        citacoes_extraidas=[
            {"indice": f.indice, "doc_id": str(f.doc_id)} for f in resposta.fontes
        ],
        recusou=resposta.recusou,
        latencia_ms=resposta.latencia_ms,
        latencia_embed_ms=resposta.latencia_embed_ms,
        latencia_busca_ms=resposta.latencia_busca_ms,
        latencia_gen_ms=resposta.latencia_gen_ms,
        uso_tokens=resposta.uso_tokens.dict(),
    )

    return ChatResponse(
        texto=resposta.texto,
        fontes=fontes_out,
        recusou=resposta.recusou,
        latencia_ms=resposta.latencia_ms,
    )
