"""
Cliente assíncrono para a API Gemini via Vertex AI.

Encapsula:
- embeddings Matryoshka-truncados em 1536 dims (para caber no HNSW do pgvector)
- geração com thinking ativado (orçamento dinâmico) + temperatura 1.0,
  recomendação oficial para o Gemini 3.1 Pro

A assimetria `task_type` entre indexação (`RETRIEVAL_DOCUMENT`) e busca
(`RETRIEVAL_QUERY`) é crítica para o recall: o mesmo texto muda de
embedding conforme a função.

A factory `get_gemini_client()` é cacheada; os serviços/rotas recebem o
cliente explicitamente (injeção), não instanciam de novo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import structlog
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


@dataclass(slots=True)
class UsoTokens:
    """Contadores de tokens de uma chamada de geração."""

    prompt: int = 0
    output: int = 0
    thinking: int = 0

    def dict(self) -> dict[str, int]:
        return {"prompt": self.prompt, "output": self.output, "thinking": self.thinking}


@dataclass(slots=True)
class RespostaGerador:
    """Retorno da geração: texto final + sumário do pensamento + tokens usados."""

    texto: str
    pensamentos_sumario: str = ""
    uso: UsoTokens = field(default_factory=UsoTokens)


class GeminiClient:
    """Wrapper fino sobre `google.genai.Client` configurado para Vertex AI."""

    def __init__(
        self,
        *,
        project: str,
        location: str,
        model_generate: str,
        model_embed: str,
        embedding_dims: int,
    ) -> None:
        self._project = project
        self._location = location
        self._model_generate = model_generate
        self._model_embed = model_embed
        self._embedding_dims = embedding_dims
        self._client = genai.Client(vertexai=True, project=project, location=location)

    # ──────────────────────────────────────
    # Embeddings
    # ──────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_text(self, texto: str, *, task_type: TaskType) -> list[float]:
        """Gera embedding para um único texto."""
        resp = await self._client.aio.models.embed_content(
            model=self._model_embed,
            contents=[texto],
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self._embedding_dims,
            ),
        )
        return list(resp.embeddings[0].values)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_batch(
        self, textos: list[str], *, task_type: TaskType
    ) -> list[list[float]]:
        """Gera embeddings em lote, preservando ordem de entrada."""
        if not textos:
            return []
        resp = await self._client.aio.models.embed_content(
            model=self._model_embed,
            contents=textos,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self._embedding_dims,
            ),
        )
        return [list(e.values) for e in resp.embeddings]

    # ──────────────────────────────────────
    # Geração com thinking
    # ──────────────────────────────────────

    async def generate_answer(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 1.0,
        thinking_budget: int = -1,
        include_thoughts: bool = True,
    ) -> RespostaGerador:
        """Gera resposta com thinking ativado.

        `thinking_budget=-1` = orçamento dinâmico (o próprio modelo decide
        quanto pensar, entre 128 e 32.768 tokens). Para Gemini 3.1 Pro, a
        temperatura recomendada com thinking ativado é 1.0.
        """
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts,
            ),
        )

        resp = await self._client.aio.models.generate_content(
            model=self._model_generate,
            contents=prompt,
            config=config,
        )

        # Extrair texto final + sumário dos pensamentos (quando include_thoughts=True,
        # as partes com `thought=True` trazem o resumo do raciocínio do modelo).
        texto_final = ""
        pensamentos = ""
        for candidate in resp.candidates or []:
            content = candidate.content
            if not content or not content.parts:
                continue
            for part in content.parts:
                if not part.text:
                    continue
                if getattr(part, "thought", False):
                    pensamentos += part.text
                else:
                    texto_final += part.text

        uso = UsoTokens()
        if resp.usage_metadata:
            uso.prompt = resp.usage_metadata.prompt_token_count or 0
            uso.output = resp.usage_metadata.candidates_token_count or 0
            uso.thinking = resp.usage_metadata.thoughts_token_count or 0

        return RespostaGerador(
            texto=texto_final.strip(),
            pensamentos_sumario=pensamentos.strip(),
            uso=uso,
        )


@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    """Factory cacheada. Dá erro claro se GCP não estiver configurado."""
    settings = get_settings()
    if not settings.gcp_project_id:
        raise RuntimeError(
            "gcp_project_id não configurado. Defina GCP_PROJECT_ID no .env "
            "ou rode `gcloud auth application-default login` antes."
        )
    return GeminiClient(
        project=settings.gcp_project_id,
        location=settings.gcp_location,
        model_generate=settings.gemini_model,
        model_embed=settings.gemini_embedding_model,
        embedding_dims=settings.gemini_embedding_dimensions,
    )


def identificador_modelo_embedding() -> str:
    """String determinística para rastrear versão de modelo/dimensão.

    Usada em `DocumentoRag.modelo_embedding` para permitir reindexar quando o
    modelo ou a dimensão mudar.
    """
    settings = get_settings()
    return f"{settings.gemini_embedding_model}@{settings.gemini_embedding_dimensions}"
