"""
Conector para a API do SICONFI (Tesouro Nacional).

API Docs: https://apidatalake.tesouro.gov.br/docs/siconfi/
Spec ORDS. Sem autenticação. REST, retorna JSON no formato
`{items, hasMore, limit, offset, count, links}`.

Endpoints da Fase 1 (RREO):
  GET /rreo — Relatório Resumido da Execução Orçamentária (bimestral)

Identificação do ente: `id_ente` = código IBGE (Jequié: 2918001).
"""

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# ORDS tem limite padrão de 5000 itens/página.
MAX_PAGE_SIZE = 5000
# Guard-rail de segurança para o loop de paginação.
MAX_ITERACOES_PAGINACAO = 50


class SICONFIClient:
    """Cliente para os endpoints do SICONFI."""

    def __init__(
        self,
        base_url: str | None = None,
        id_ente: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.siconfi_base_url).rstrip("/")
        self.id_ente = id_ente or settings.siconfi_id_ente_jequie
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SICONFIClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60.0,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with SICONFIClient() as client:' para inicializar.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _get(self, endpoint: str, params: dict) -> dict:
        """Requisição GET com retry automático."""
        response = await self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()

    async def rreo(
        self,
        *,
        an_exercicio: int,
        nr_periodo: int,
        no_anexo: str | None = None,
    ) -> dict:
        """
        Consulta o Relatório Resumido da Execução Orçamentária.

        GET /rreo
        Parâmetros:
          - an_exercicio: ano (ex: 2024)
          - nr_periodo: bimestre (1-6)
          - no_anexo: anexo específico (opcional; None traz todos)
        """
        params: dict[str, Any] = {
            "an_exercicio": an_exercicio,
            "nr_periodo": nr_periodo,
            "co_tipo_demonstrativo": "RREO",
            "id_ente": self.id_ente,
        }
        if no_anexo:
            params["no_anexo"] = no_anexo
        logger.info(
            "siconfi.rreo",
            exercicio=an_exercicio,
            periodo=nr_periodo,
            anexo=no_anexo,
        )
        return await self._get("/rreo", params)

    async def paginar_rreo(
        self,
        *,
        an_exercicio: int,
        nr_periodo: int,
        no_anexo: str | None = None,
    ) -> list[dict]:
        """
        Consome todas as páginas do RREO para um (exercício, período),
        retornando a lista achatada de items.

        Resposta ORDS: `{items, hasMore, limit, offset, count, links}`.
        Pagina via `offset`; interrompe quando `hasMore` for falso ou
        não houver mais items.
        """
        todos: list[dict] = []
        offset = 0

        for iteracao in range(MAX_ITERACOES_PAGINACAO):
            params: dict[str, Any] = {
                "an_exercicio": an_exercicio,
                "nr_periodo": nr_periodo,
                "co_tipo_demonstrativo": "RREO",
                "id_ente": self.id_ente,
                "offset": offset,
            }
            if no_anexo:
                params["no_anexo"] = no_anexo

            resultado = await self._get("/rreo", params)
            items = resultado.get("items", []) or []
            if not items:
                break

            todos.extend(items)

            if not resultado.get("hasMore"):
                break

            # ORDS retorna limit da página corrente; usar como incremento do offset.
            limit = resultado.get("limit") or len(items)
            offset += limit

            if iteracao == MAX_ITERACOES_PAGINACAO - 1:
                logger.warning(
                    "siconfi.paginacao_limite",
                    exercicio=an_exercicio,
                    periodo=nr_periodo,
                    iteracoes=iteracao + 1,
                )

        logger.info(
            "siconfi.rreo.paginacao_completa",
            exercicio=an_exercicio,
            periodo=nr_periodo,
            total=len(todos),
        )
        return todos
