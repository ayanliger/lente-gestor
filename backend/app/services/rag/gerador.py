"""
Gerador — orquestra o ciclo completo:

    pergunta → retrieval → prompt com docs numerados → Gemini (thinking) →
    parser de citações → RespostaChat

Pontos-chave:
- Citações são `[n]` por índice 1-based do documento no prompt. Quem
  alucinar um índice inexistente tem a citação descartada (defense-in-depth).
- Marcador `NAO_SEI` na resposta → vira `RespostaChat.recusou=True`, sem
  fontes. Isso é intencional: melhor recusar do que alucinar.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.client import GeminiClient, UsoTokens
from app.services.rag.prompts import (
    MARCADOR_RECUSA,
    build_system_prompt,
    montar_prompt_usuario,
)
from app.services.rag.recuperacao import DocumentoRelevante, buscar

logger = structlog.get_logger()

# Regex para capturar citações `[n]` ou `[n, m]` ou `[n][m]` na resposta.
# Aceita 1-2 dígitos para permitir k até 99 sem surpresa.
_RE_CITACAO = re.compile(r"\[(\d{1,2})\]")


@dataclass(slots=True)
class FonteCitada:
    """Documento efetivamente citado na resposta."""

    indice: int
    doc_id: uuid.UUID
    fonte: str
    referencia_tipo: str
    referencia_id: uuid.UUID | None
    chave_unica: str
    titulo: str
    metadados: dict[str, Any]
    score: float


@dataclass(slots=True)
class RespostaChat:
    """Resultado do ciclo completo de RAG."""

    texto: str
    fontes: list[FonteCitada]
    recusou: bool
    latencia_ms: int
    latencia_embed_ms: int
    latencia_busca_ms: int
    latencia_gen_ms: int
    uso_tokens: UsoTokens
    docs_recuperados: list[DocumentoRelevante] = field(default_factory=list)
    pensamentos_sumario: str = ""


def parse_citacoes(
    texto: str, docs: list[DocumentoRelevante]
) -> list[FonteCitada]:
    """Extrai citações `[n]` do texto e mapeia para documentos válidos.

    - Ignora índices duplicados (preserva ordem de primeira aparição).
    - Descarta índices fora do range de `docs` (hallucination defense).
    """
    vistos: set[int] = set()
    fontes: list[FonteCitada] = []
    for m in _RE_CITACAO.finditer(texto):
        idx = int(m.group(1))
        if idx in vistos:
            continue
        vistos.add(idx)
        if idx < 1 or idx > len(docs):
            continue
        doc = docs[idx - 1]
        fontes.append(
            FonteCitada(
                indice=idx,
                doc_id=doc.doc_id,
                fonte=doc.fonte,
                referencia_tipo=doc.referencia_tipo,
                referencia_id=doc.referencia_id,
                chave_unica=doc.chave_unica,
                titulo=doc.titulo,
                metadados=doc.metadados,
                score=doc.score,
            )
        )
    return fontes


async def responder(
    pergunta: str,
    *,
    db: AsyncSession,
    cliente: GeminiClient,
    k: int = 6,
) -> RespostaChat:
    """Responde a uma pergunta usando o ciclo completo de RAG."""
    t_inicio = time.perf_counter()

    # ── Retrieval (embed + busca) ──
    t_embed_inicio = time.perf_counter()
    # A busca internamente gera o embedding da pergunta; medimos juntos
    # e dividimos depois via heurística: primeira medição global.
    docs = await buscar(pergunta, db=db, cliente=cliente, k=k)
    t_embed_fim = time.perf_counter()

    latencia_embed_busca_ms = int((t_embed_fim - t_embed_inicio) * 1000)
    # Sem instrumentação mais fina dentro de `buscar`, dividimos 50/50 como
    # heurística honesta para o log. A instrumentação exata fica para Fase 2.
    latencia_embed_ms = latencia_embed_busca_ms // 2
    latencia_busca_ms = latencia_embed_busca_ms - latencia_embed_ms

    # ── Geração ──
    prompt_usuario = montar_prompt_usuario(pergunta, docs)
    t_gen_inicio = time.perf_counter()
    resp = await cliente.generate_answer(prompt_usuario, system=build_system_prompt())
    t_gen_fim = time.perf_counter()
    latencia_gen_ms = int((t_gen_fim - t_gen_inicio) * 1000)

    texto = resp.texto.strip()
    recusou = MARCADOR_RECUSA in texto

    # Se recusou, não processa citações (apresenta mensagem limpa no frontend).
    if recusou:
        fontes: list[FonteCitada] = []
    else:
        fontes = parse_citacoes(texto, docs)

    latencia_total_ms = int((time.perf_counter() - t_inicio) * 1000)

    return RespostaChat(
        texto=texto,
        fontes=fontes,
        recusou=recusou,
        latencia_ms=latencia_total_ms,
        latencia_embed_ms=latencia_embed_ms,
        latencia_busca_ms=latencia_busca_ms,
        latencia_gen_ms=latencia_gen_ms,
        uso_tokens=resp.uso,
        docs_recuperados=docs,
        pensamentos_sumario=resp.pensamentos_sumario,
    )


__all__ = ["responder", "parse_citacoes", "RespostaChat", "FonteCitada"]
