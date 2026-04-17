"""
Conector para as APIs de serviço do IBGE.

- `/v1/localidades/municipios/{cod}` — metadados aninhados do município.
- `/v3/agregados/{agg}/periodos/-N/variaveis/{var}?localidades=N6[{cod}]` — SIDRA,
  retornando uma lista com `resultados[0].series[0].serie` como dict ano→valor.

Sem autenticação. REST, retorna JSON.
"""

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Identificadores das tabelas SIDRA usadas
AGREGADO_POPULACAO = 6579  # População residente estimada
VARIAVEL_POPULACAO = 9324

AGREGADO_PIB = 5938  # Produto Interno Bruto dos Municípios
VARIAVEL_PIB = 37  # PIB a preços correntes (unidade: Mil Reais)


class IBGEClient:
    """Cliente para endpoints de localidades e SIDRA (agregados)."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ibge_base_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "IBGEClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with IBGEClient() as client:' para inicializar.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
    )
    async def _get(self, endpoint: str) -> dict | list:
        """Requisição GET com retry automático."""
        response = await self.client.get(endpoint)
        response.raise_for_status()
        return response.json()

    async def municipio(self, codigo_ibge: str) -> dict:
        """Metadados do município (nome, UF, microrregião, mesorregião)."""
        logger.info("ibge.municipio", codigo_ibge=codigo_ibge)
        result = await self._get(f"/v1/localidades/municipios/{codigo_ibge}")
        if not isinstance(result, dict):
            raise ValueError(f"Resposta inesperada para município {codigo_ibge}")
        return result

    async def populacao(self, codigo_ibge: str, ultimos_periodos: int = 10) -> list:
        """
        Série histórica de população estimada.

        Tabela SIDRA 6579, variável 9324 ("População residente estimada").
        """
        path = (
            f"/v3/agregados/{AGREGADO_POPULACAO}/periodos/-{ultimos_periodos}"
            f"/variaveis/{VARIAVEL_POPULACAO}?localidades=N6[{codigo_ibge}]"
        )
        logger.info("ibge.populacao", codigo_ibge=codigo_ibge, ultimos=ultimos_periodos)
        result = await self._get(path)
        if not isinstance(result, list):
            raise ValueError(f"Resposta inesperada para população {codigo_ibge}")
        return result

    async def pib(self, codigo_ibge: str, ultimos_periodos: int = 10) -> list:
        """
        Série histórica de PIB municipal a preços correntes.

        Tabela SIDRA 5938, variável 37. Valores em MIL REAIS.
        """
        path = (
            f"/v3/agregados/{AGREGADO_PIB}/periodos/-{ultimos_periodos}"
            f"/variaveis/{VARIAVEL_PIB}?localidades=N6[{codigo_ibge}]"
        )
        logger.info("ibge.pib", codigo_ibge=codigo_ibge, ultimos=ultimos_periodos)
        result = await self._get(path)
        if not isinstance(result, list):
            raise ValueError(f"Resposta inesperada para PIB {codigo_ibge}")
        return result
