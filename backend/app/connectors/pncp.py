"""
Conector para a API do PNCP (Portal Nacional de Contratações Públicas).

API Docs: https://pncp.gov.br/api/consulta/swagger-ui/index.html
Sem autenticação. REST, retorna JSON.

Limitações conhecidas (Transparência Brasil, 2024):
- Paginação limitada
- Campos com preenchimento nulo
- Fragmentação de dados entre endpoints
- Impossibilidade de rastrear contratos por item individual
"""

from datetime import date

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Limites da API
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50


class PNCPClient:
    """Cliente para consumo da API REST do PNCP."""

    def __init__(
        self,
        base_url: str | None = None,
        cnpj: str | None = None,
    ):
        self.base_url = (base_url or settings.pncp_base_url).rstrip("/")
        self.cnpj = cnpj or settings.pncp_cnpj_jequie
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with PNCPClient() as client:' para inicializar.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Requisição GET com retry automático."""
        response = await self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()

    async def listar_contratacoes(
        self,
        data_inicial: date,
        data_final: date,
        pagina: int = 1,
        tamanho_pagina: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Lista contratações publicadas por período.

        GET /contratacoes/publicacao
        """
        params = {
            "dataInicial": data_inicial.strftime("%Y%m%d"),
            "dataFinal": data_final.strftime("%Y%m%d"),
            "cnpjOrgao": self.cnpj,
            "pagina": pagina,
            "tamanhoPagina": min(tamanho_pagina, MAX_PAGE_SIZE),
        }
        logger.info(
            "pncp.contratacoes",
            data_inicial=str(data_inicial),
            data_final=str(data_final),
            pagina=pagina,
        )
        return await self._get("/contratacoes/publicacao", params=params)

    async def listar_contratos(
        self,
        data_inicial: date,
        data_final: date,
        pagina: int = 1,
        tamanho_pagina: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Lista contratos publicados por período.

        GET /contratos/publicacao
        """
        params = {
            "dataInicial": data_inicial.strftime("%Y%m%d"),
            "dataFinal": data_final.strftime("%Y%m%d"),
            "cnpjOrgao": self.cnpj,
            "pagina": pagina,
            "tamanhoPagina": min(tamanho_pagina, MAX_PAGE_SIZE),
        }
        logger.info(
            "pncp.contratos",
            data_inicial=str(data_inicial),
            data_final=str(data_final),
            pagina=pagina,
        )
        return await self._get("/contratos/publicacao", params=params)

    async def listar_pca(
        self,
        ano_exercicio: int,
        pagina: int = 1,
        tamanho_pagina: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Lista itens do Plano de Contratações Anual (PCA).

        GET /pca/v2/itens
        """
        params = {
            "cnpjOrgao": self.cnpj,
            "anoExercicio": ano_exercicio,
            "pagina": pagina,
            "tamanhoPagina": min(tamanho_pagina, MAX_PAGE_SIZE),
        }
        logger.info("pncp.pca", ano=ano_exercicio, pagina=pagina)
        return await self._get("/pca/v2/itens", params=params)

    async def listar_atas(
        self,
        data_inicial: date,
        data_final: date,
        pagina: int = 1,
        tamanho_pagina: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Lista atas de registro de preço.

        GET /atas
        """
        params = {
            "dataInicial": data_inicial.strftime("%Y%m%d"),
            "dataFinal": data_final.strftime("%Y%m%d"),
            "cnpjOrgao": self.cnpj,
            "pagina": pagina,
            "tamanhoPagina": min(tamanho_pagina, MAX_PAGE_SIZE),
        }
        logger.info(
            "pncp.atas",
            data_inicial=str(data_inicial),
            data_final=str(data_final),
            pagina=pagina,
        )
        return await self._get("/atas", params=params)

    async def paginar_todos(
        self,
        metodo,
        **kwargs,
    ) -> list[dict]:
        """
        Consome todas as páginas de um endpoint, retornando a lista completa.

        Trata a paginação automaticamente.
        """
        todos = []
        pagina = 1
        kwargs["tamanho_pagina"] = MAX_PAGE_SIZE

        while True:
            resultado = await metodo(pagina=pagina, **kwargs)

            # A estrutura de resposta do PNCP varia por endpoint.
            # Normalizar conforme documentação real durante implementação.
            dados = resultado.get("data", resultado.get("items", []))
            if not dados:
                break

            todos.extend(dados)
            pagina += 1

            # Safety: evitar loops infinitos
            if pagina > 100:
                logger.warning("pncp.paginacao_limite", paginas=pagina)
                break

        logger.info("pncp.paginacao_completa", total_registros=len(todos))
        return todos
