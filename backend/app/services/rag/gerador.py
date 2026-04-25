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
import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import FonteDocumento
from app.services.rag.client import GeminiClient, UsoTokens
from app.services.rag.cobertura import (
    gerar_documento_cobertura,
    pergunta_pede_cobertura,
)
from app.services.rag.prompts import (
    MARCADOR_RECUSA,
    build_system_prompt,
    montar_prompt_usuario,
)
from app.services.rag.recuperacao import DocumentoRelevante, buscar, buscar_por_chaves

logger = structlog.get_logger()

# Regex para capturar citações `[n]` ou `[n, m]` ou `[n][m]` na resposta.
# Aceita 1-2 dígitos para permitir k até 99 sem surpresa.
_RE_CITACAO = re.compile(r"\[(\d{1,2})\]")

_CANDIDATE_K_PADRAO = 18
_CANDIDATE_K_AMPLO = 30
_PROMPT_K_PADRAO = 8
_PROMPT_K_AMPLO = 12

_FONTES_ORCAMENTO = (
    FonteDocumento.RESUMO_FUNCAO,
    FonteDocumento.RESUMO_RECEITA,
    FonteDocumento.RESUMO_NATUREZA_DESPESA,
    FonteDocumento.INDICADOR_FISCAL,
)

_TERMOS_PERGUNTA_AMPLA = (
    "panorama",
    "visao geral",
    "visão geral",
    "resumo",
    "comparar",
    "comparando",
    "cruzamento",
    "principais",
    "tendencia",
    "tendência",
)


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


def _campo_turno(turno: Any, campo: str, default: Any = None) -> Any:
    if isinstance(turno, dict):
        return turno.get(campo, default)
    return getattr(turno, campo, default)


def _historico_recente(historico: Sequence[Any] | None) -> list[Any]:
    return list(historico or [])[-6:]


def _limitar_texto(texto: str, limite: int) -> str:
    texto = texto.strip()
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def _formatar_historico_prompt(historico: Sequence[Any]) -> str:
    partes: list[str] = []
    for turno in historico[-6:]:
        autor = _campo_turno(turno, "autor", "usuario")
        texto = _limitar_texto(str(_campo_turno(turno, "texto", "")), 700)
        fontes = _campo_turno(turno, "fontes", []) or []
        if not texto:
            continue
        sufixo_fontes = ""
        if fontes:
            sufixo_fontes = f" Fontes citadas: {', '.join(map(str, fontes[:6]))}."
        partes.append(f"{autor}: {texto}{sufixo_fontes}")
    return "\n".join(partes)


def _montar_consulta_recuperacao(pergunta: str, historico: Sequence[Any]) -> str:
    """Combina pergunta atual com contexto recente para resolver follow-ups."""
    partes = ["Pergunta atual:", pergunta.strip()]
    historico_prompt = _formatar_historico_prompt(historico[-4:])
    if historico_prompt:
        partes.extend(["Contexto recente da conversa:", historico_prompt])
    return "\n".join(partes)


def _chaves_fontes_historico(historico: Sequence[Any]) -> list[str]:
    chaves: list[str] = []
    for turno in historico:
        fontes = _campo_turno(turno, "fontes", []) or []
        for fonte in fontes:
            chave = str(fonte).strip()
            if chave:
                chaves.append(chave)
    return list(dict.fromkeys(chaves))[-12:]


def _pergunta_ampla(pergunta: str) -> bool:
    normalizada = _normalizar(pergunta)
    return any(_normalizar(termo) in normalizada for termo in _TERMOS_PERGUNTA_AMPLA)


def _normalizar(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acentos if not unicodedata.combining(c)).lower()


def _chave_entidade(doc: DocumentoRelevante) -> tuple[str, str]:
    metadados = doc.metadados or {}
    entidade = (
        metadados.get("funcao")
        or metadados.get("categoria_legivel")
        or metadados.get("natureza_legivel")
        or metadados.get("codigo")
        or metadados.get("fornecedor_nome")
        or doc.chave_unica
    )
    return (doc.fonte, str(entidade))


def _selecionar_docs(
    candidatos: list[DocumentoRelevante],
    *,
    limite: int,
    diversificar: bool,
) -> list[DocumentoRelevante]:
    """Deduplica e limita candidatos; em modo amplo diversifica entidades."""
    sem_repetir: list[DocumentoRelevante] = []
    chaves_vistas: set[str] = set()
    for doc in candidatos:
        if doc.chave_unica in chaves_vistas:
            continue
        chaves_vistas.add(doc.chave_unica)
        sem_repetir.append(doc)

    if not diversificar:
        return sem_repetir[:limite]

    selecionados: list[DocumentoRelevante] = []
    entidades_vistas: set[tuple[str, str]] = set()
    for doc in sem_repetir:
        entidade = _chave_entidade(doc)
        if entidade in entidades_vistas:
            continue
        entidades_vistas.add(entidade)
        selecionados.append(doc)
        if len(selecionados) >= limite:
            return selecionados

    for doc in sem_repetir:
        if doc in selecionados:
            continue
        selecionados.append(doc)
        if len(selecionados) >= limite:
            break
    return selecionados


def _combinar_contexto(
    prioritarios: list[DocumentoRelevante],
    candidatos: list[DocumentoRelevante],
    *,
    limite: int,
    diversificar: bool,
) -> list[DocumentoRelevante]:
    docs: list[DocumentoRelevante] = []
    chaves_vistas: set[str] = set()

    for doc in prioritarios:
        if doc.chave_unica in chaves_vistas:
            continue
        docs.append(doc)
        chaves_vistas.add(doc.chave_unica)
        if len(docs) >= limite:
            return docs

    restantes = [d for d in candidatos if d.chave_unica not in chaves_vistas]
    docs.extend(
        _selecionar_docs(
            restantes,
            limite=limite - len(docs),
            diversificar=diversificar,
        )
    )
    return docs


async def responder(
    pergunta: str,
    *,
    db: AsyncSession,
    cliente: GeminiClient,
    k: int = 6,
    historico: Sequence[Any] | None = None,
) -> RespostaChat:
    """Responde a uma pergunta usando o ciclo completo de RAG."""
    t_inicio = time.perf_counter()
    historico_recente = _historico_recente(historico)
    modo_cobertura = pergunta_pede_cobertura(pergunta)
    modo_amplo = modo_cobertura or _pergunta_ampla(pergunta)
    consulta_recuperacao = _montar_consulta_recuperacao(pergunta, historico_recente)
    candidate_k = max(k, _CANDIDATE_K_AMPLO if modo_amplo else _CANDIDATE_K_PADRAO)
    prompt_k = max(k, _PROMPT_K_AMPLO if modo_amplo else _PROMPT_K_PADRAO)

    # ── Retrieval (embed + busca) ──
    t_embed_inicio = time.perf_counter()
    prioritarios: list[DocumentoRelevante] = []
    chaves_historico = _chaves_fontes_historico(historico_recente)
    if modo_cobertura or "cobertura:orcamento" in chaves_historico:
        prioritarios.append(await gerar_documento_cobertura(db))
    chaves_persistidas = [
        chave for chave in chaves_historico if chave != "cobertura:orcamento"
    ]
    prioritarios.extend(await buscar_por_chaves(chaves_persistidas, db=db, score=0.99))

    candidatos = await buscar(
        consulta_recuperacao,
        db=db,
        cliente=cliente,
        k=candidate_k,
        fontes=_FONTES_ORCAMENTO if modo_cobertura else None,
        fallback_minimo=prompt_k if modo_amplo else None,
        aplicar_limiar=not modo_amplo,
    )
    docs = _combinar_contexto(
        prioritarios,
        candidatos,
        limite=prompt_k,
        diversificar=modo_amplo,
    )
    t_embed_fim = time.perf_counter()

    latencia_embed_busca_ms = int((t_embed_fim - t_embed_inicio) * 1000)
    # Sem instrumentação mais fina dentro de `buscar`, dividimos 50/50 como
    # heurística honesta para o log. A instrumentação exata fica para Fase 2.
    latencia_embed_ms = latencia_embed_busca_ms // 2
    latencia_busca_ms = latencia_embed_busca_ms - latencia_embed_ms

    # ── Geração ──
    prompt_usuario = montar_prompt_usuario(
        pergunta,
        docs,
        historico=_formatar_historico_prompt(historico_recente),
    )
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
