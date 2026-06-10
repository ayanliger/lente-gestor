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

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

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
    """Wrapper fino sobre `google.genai.Client` configurado para Vertex AI.

    Usa dois clientes internos em regiões diferentes:
    - `_embed_client` (regional, ex: us-central1) para `gemini-embedding-*`
    - `_gen_client` (global) para a família Gemini 3.1 preview, que
      é servida exclusivamente pelo endpoint global
    Se as duas regiões forem iguais, as instâncias separadas ainda funcionam
    (custo zero, só pra manter o código uniforme).
    """

    def __init__(
        self,
        *,
        project: str,
        location_embed: str,
        location_generate: str,
        model_generate: str,
        model_embed: str,
        embedding_dims: int,
    ) -> None:
        self._project = project
        self._location_embed = location_embed
        self._location_generate = location_generate
        self._model_generate = model_generate
        self._model_embed = model_embed
        self._embedding_dims = embedding_dims
        self._embed_client = genai.Client(
            vertexai=True, project=project, location=location_embed
        )
        self._gen_client = genai.Client(
            vertexai=True, project=project, location=location_generate
        )

    # ──────────────────────────────────────
    # Embeddings
    # ──────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_text(self, texto: str, *, task_type: TaskType) -> list[float]:
        """Gera embedding para um único texto."""
        resp = await self._embed_client.aio.models.embed_content(
            model=self._model_embed,
            contents=[texto],
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self._embedding_dims,
            ),
        )
        return list(resp.embeddings[0].values)

    async def embed_batch(
        self, textos: list[str], *, task_type: TaskType
    ) -> list[list[float]]:
        """Gera embeddings em paralelo, preservando ordem de entrada.

        O endpoint Gemini via Vertex AI processa um texto por chamada —
        passar uma lista em `contents` será tratado como input único. Usamos
        `asyncio.gather` para rodar N chamadas concorrentes; cada uma já
        tem retry exponencial via `embed_text`. O `Semaphore` limita a
        concorrência para respeitar quotas da API.
        """
        import asyncio

        if not textos:
            return []
        sem = asyncio.Semaphore(8)  # 8 chamadas concorrentes é conservador

        async def _um(t: str) -> list[float]:
            async with sem:
                return await self.embed_text(t, task_type=task_type)

        return await asyncio.gather(*(_um(t) for t in textos))

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

        resp = await self._gen_client.aio.models.generate_content(
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

    # ──────────────────────────────────────
    # Geração com function calling
    # ──────────────────────────────────────

    async def generate_answer_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list[types.Tool],
        tool_executors: dict[
            str, Callable[..., Awaitable[dict[str, Any]]]
        ],
        max_iterations: int = 3,
        temperature: float = 1.0,
        thinking_budget: int = -1,
        include_thoughts: bool = True,
    ) -> RespostaGerador:
        """Geração com function calling: o modelo pode invocar tools até
        produzir texto final.

        Loop:
        1. Envia o `prompt` com `tools` declaradas.
        2. Se a resposta contém `function_call` parts, executa cada um via
           `tool_executors` e devolve `function_response` na próxima rodada.
        3. Repete até o modelo retornar somente texto ou atingir
           `max_iterations`.

        `tool_executors` recebe os argumentos do `function_call` como
        kwargs e retorna um dict JSON-serializável que vira o
        `function_response.response`. Efeitos colaterais (ex: agregar
        documentos para citação) são responsabilidade do caller via
        closures.
        """
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            tools=tools,
            thinking_config=types.ThinkingConfig(
                thinking_budget=thinking_budget,
                include_thoughts=include_thoughts,
            ),
        )

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=prompt)])
        ]

        uso_total = UsoTokens()
        pensamentos_total = ""
        texto_final = ""
        chamadas_realizadas: list[str] = []

        for iteracao in range(max_iterations + 1):
            resp = await self._gen_client.aio.models.generate_content(
                model=self._model_generate,
                contents=contents,
                config=config,
            )

            if resp.usage_metadata:
                uso_total.prompt += resp.usage_metadata.prompt_token_count or 0
                uso_total.output += (
                    resp.usage_metadata.candidates_token_count or 0
                )
                uso_total.thinking += (
                    resp.usage_metadata.thoughts_token_count or 0
                )

            candidate = (resp.candidates or [None])[0]
            if candidate is None or not candidate.content:
                break

            partes = candidate.content.parts or []
            function_calls: list[types.FunctionCall] = []
            texto_iter = ""
            for part in partes:
                if getattr(part, "function_call", None):
                    function_calls.append(part.function_call)
                elif part.text:
                    if getattr(part, "thought", False):
                        pensamentos_total += part.text
                    else:
                        texto_iter += part.text

            if not function_calls:
                texto_final = texto_iter
                break

            # Última iteração permitida: o modelo ainda quis chamar tool,
            # mas não vamos executar mais — usamos o texto que veio (se
            # houver) e abortamos.
            if iteracao >= max_iterations:
                logger.warning(
                    "rag.tools.max_iter",
                    iteracoes=iteracao,
                    chamadas_realizadas=chamadas_realizadas,
                    pendentes=[fc.name for fc in function_calls],
                )
                texto_final = texto_iter
                break

            # Anexa a resposta do modelo ao histórico antes de devolver os
            # function_responses — protocolo padrão do Gemini.
            contents.append(candidate.content)

            # Executa cada tool e gera a Content com function_response parts.
            response_parts: list[types.Part] = []
            for fc in function_calls:
                chamadas_realizadas.append(fc.name)
                executor = tool_executors.get(fc.name)
                if executor is None:
                    response = {
                        "erro": (
                            f"Ferramenta {fc.name!r} indisponível. "
                            f"Tools válidas: {sorted(tool_executors)}."
                        )
                    }
                else:
                    try:
                        kwargs = dict(fc.args or {})
                        response = await executor(**kwargs)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception(
                            "rag.tools.exec_error",
                            tool=fc.name,
                            args=dict(fc.args or {}),
                        )
                        response = {
                            "erro": (
                                f"Erro ao executar {fc.name!r}: {exc}."
                            )
                        }
                response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response=response,
                        )
                    )
                )
            contents.append(types.Content(role="user", parts=response_parts))

        return RespostaGerador(
            texto=texto_final.strip(),
            pensamentos_sumario=pensamentos_total.strip(),
            uso=uso_total,
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
        location_embed=settings.gcp_location,
        location_generate=settings.gcp_location_generate,
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
