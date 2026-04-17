"""
Conector para a API do PNCP (Portal Nacional de Contratações Públicas).

API Docs: https://pncp.gov.br/api/consulta/swagger-ui/index.html
Spec: https://pncp.gov.br/api/consulta/v3/api-docs
Sem autenticação. REST, retorna JSON.

Endpoints validados (abril 2026):
  GET /v1/contratacoes/publicacao — requer codigoModalidadeContratacao, filtro por cnpj
  GET /v1/contratos               — filtro por cnpjOrgao, max 365 dias
  GET /v1/atas                    — atas de registro de preço

Limitações conhecidas (Transparência Brasil, 2024):
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
# Contratacoes requer tamanhoPagina >= 10; contratos aceita qualquer valor.
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50
MIN_PAGE_SIZE = 10

# Modalidades de contratação relevantes para municípios
MODALIDADES = {
    4: "Concorrência",
    5: "Pregão Eletrônico",
    6: "Pregão Presencial",
    7: "Inexigibilidade",
    8: "Dispensa",
}


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
            timeout=60.0,
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
        codigo_modalidade: int = 8,
        pagina: int = 1,
        tamanho_pagina: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Lista contratações publicadas por período e modalidade.

        GET /contratacoes/publicacao
        Parâmetro de filtro por órgão: cnpj (não cnpjOrgao).
        codigoModalidadeContratacao é obrigatório.
        """
        params = {
            "dataInicial": data_inicial.strftime("%Y%m%d"),
            "dataFinal": data_final.strftime("%Y%m%d"),
            "codigoModalidadeContratacao": codigo_modalidade,
            "cnpj": self.cnpj,
            "pagina": pagina,
            "tamanhoPagina": max(MIN_PAGE_SIZE, min(tamanho_pagina, MAX_PAGE_SIZE)),
        }
        logger.info(
            "pncp.contratacoes",
            data_inicial=str(data_inicial),
            data_final=str(data_final),
            modalidade=codigo_modalidade,
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

        GET /contratos (não /contratos/publicacao).
        Máximo 365 dias por requisição.
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
        return await self._get("/contratos", params=params)

    async def paginar_todos(
        self,
        metodo,
        tamanho_pagina: int = MAX_PAGE_SIZE,
        **kwargs,
    ) -> list[dict]:
        """
        Consome todas as páginas de um endpoint, retornando a lista completa.

        Resposta PNCP: {data: [...], totalRegistros, totalPaginas, numeroPagina, empty}
        """
        todos = []
        pagina = 1
        kwargs["tamanho_pagina"] = tamanho_pagina

        while True:
            resultado = await metodo(pagina=pagina, **kwargs)

            dados = resultado.get("data", [])
            if not dados:
                break

            todos.extend(dados)

            total_paginas = resultado.get("totalPaginas", 1)
            if pagina >= total_paginas:
                break

            pagina += 1

            if pagina > 200:
                logger.warning("pncp.paginacao_limite", paginas=pagina)
                break

        logger.info("pncp.paginacao_completa", total_registros=len(todos))
        return todos
