"""Fixtures compartilhadas para testes."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.main import app
from app.api.deps import get_db


# ──────────────────────────────────────────
# Banco de testes
# ──────────────────────────────────────────

TEST_DATABASE_URL = "postgresql+asyncpg://lente:lente_dev@localhost:5432/lente"


@pytest.fixture
async def db_session():
    """Sessão isolada — rollback automático após cada teste.

    Cria engine fresh por teste (NullPool) para evitar conflito de event loop.
    Toda escrita é revertida ao final.
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        yield session

        await trans.rollback()
        await session.close()
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    """Cliente HTTP de teste com DB injetado."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ──────────────────────────────────────────
# Fixtures: dados PNCP simulados
# ──────────────────────────────────────────

# CNPJs de teste — não colidem com dados reais ingeridos
TEST_CNPJ_ORGAO = "99000000000100"
TEST_CNPJ_FORNECEDOR = "88000000000100"

SAMPLE_CONTRATACAO_RAW = {
    "numeroControlePNCP": f"{TEST_CNPJ_ORGAO}-1-000999/2025",
    "sequencialCompra": 999,
    "anoCompra": 2025,
    "processo": "TEST-100/2025",
    "objetoCompra": "Aquisição de equipamentos de informática (TESTE)",
    "modalidadeNome": "Pregão - Eletrônico",
    "modalidadeId": 5,
    "tipoInstrumentoConvocatorioNome": "Edital",
    "valorTotalEstimado": 150000.00,
    "valorTotalHomologado": 142000.00,
    "situacaoCompraNome": "Homologada",
    "dataPublicacaoPncp": "2025-03-15T10:00:00",
    "dataAberturaProposta": "2025-03-25T09:00:00",
    "orgaoEntidade": {
        "cnpj": TEST_CNPJ_ORGAO,
        "razaoSocial": "ORGAO TESTE",
        "esferaId": "M",
        "poderId": "E",
    },
}

SAMPLE_CONTRATO_RAW = {
    "numeroControlePNCP": f"{TEST_CNPJ_ORGAO}-2-000999/2025",
    "numeroControlePncpCompra": f"{TEST_CNPJ_ORGAO}-1-000999/2025",
    "numeroContratoEmpenho": "CONTRATO N° TEST-001/2025",
    "anoContrato": 2025,
    "sequencialContrato": 999,
    "objetoContrato": "Fornecimento de computadores (TESTE)",
    "valorInicial": 142000.00,
    "valorGlobal": 142000.00,
    "valorParcela": 0.0,
    "valorAcumulado": 0.0,
    "dataAssinatura": "2025-04-01",
    "dataVigenciaInicio": "2025-04-01",
    "dataVigenciaFim": "2026-04-01",
    "dataPublicacaoPncp": "2025-04-02T11:00:00",
    "niFornecedor": TEST_CNPJ_FORNECEDOR,
    "nomeRazaoSocialFornecedor": "EMPRESA TESTE LTDA",
    "tipoPessoa": "PJ",
    "categoriaProcesso": {"id": 2, "nome": "Compras"},
    "orgaoEntidade": {
        "cnpj": TEST_CNPJ_ORGAO,
        "razaoSocial": "ORGAO TESTE",
        "esferaId": "M",
        "poderId": "E",
    },
}

SAMPLE_PNCP_PAGE_RESPONSE = {
    "data": [SAMPLE_CONTRATACAO_RAW],
    "totalRegistros": 1,
    "totalPaginas": 1,
    "numeroPagina": 1,
    "paginasRestantes": 0,
    "empty": False,
}


@pytest.fixture
def contratacao_raw():
    return SAMPLE_CONTRATACAO_RAW.copy()


@pytest.fixture
def contrato_raw():
    return SAMPLE_CONTRATO_RAW.copy()


# ────────────────────────────────────────
# Fixtures: dados SICONFI simulados (RREO)
# ────────────────────────────────────────

# Payload real capturado de
# /ords/siconfi/tt/rreo?an_exercicio=2024&nr_periodo=6&id_ente=2918001
SAMPLE_RREO_ITEM = {
    "exercicio": 2024,
    "demonstrativo": "RREO",
    "periodo": 6,
    "periodicidade": "B",
    "instituicao": "Prefeitura Municipal de Jequié - BA",
    "cod_ibge": 2918001,
    "uf": "BA",
    "populacao": 156408,
    "anexo": "RREO-Anexo 02",
    "esfera": "M",
    "rotulo": "Total das Despesas Exceto Intra-Orçamentárias",
    "coluna": "DOTAÇÃO INICIAL",
    "cod_conta": "RREO2TotalDespesas",
    "conta": "Saúde",
    "valor": 125430789.15,
}


@pytest.fixture
def rreo_item():
    return SAMPLE_RREO_ITEM.copy()


# ────────────────────────────────────────
# Fixtures: payloads IBGE simulados
# ────────────────────────────────────────

# Capturado de /v1/localidades/municipios/2918001
SAMPLE_IBGE_MUNICIPIO = {
    "id": 2918001,
    "nome": "Jequié",
    "microrregiao": {
        "id": 29024,
        "nome": "Jequié",
        "mesorregiao": {
            "id": 2906,
            "nome": "Centro Sul Baiano",
            "UF": {
                "id": 29,
                "sigla": "BA",
                "nome": "Bahia",
                "regiao": {"id": 2, "sigla": "NE", "nome": "Nordeste"},
            },
        },
    },
    "regiao-imediata": {
        "id": 290012,
        "nome": "Jequié",
        "regiao-intermediaria": {
            "id": 2904,
            "nome": "Vitória da Conquista",
            "UF": {"id": 29, "sigla": "BA", "nome": "Bahia"},
        },
    },
}

# Payload SIDRA simplificado (estrutura real da v3, dados reais de Jequié).
SAMPLE_IBGE_POPULACAO = [
    {
        "id": "9324",
        "variavel": "População residente estimada",
        "unidade": "Pessoas",
        "resultados": [
            {
                "classificacoes": [],
                "series": [
                    {
                        "localidade": {
                            "id": "2918001",
                            "nivel": {"id": "N6", "nome": "Município"},
                            "nome": "Jequié (BA)",
                        },
                        "serie": {
                            "2020": "156126",
                            "2021": "156277",
                            "2024": "168733",
                        },
                    }
                ],
            }
        ],
    }
]

SAMPLE_IBGE_PIB = [
    {
        "id": "37",
        "variavel": "Produto Interno Bruto a preços correntes",
        "unidade": "Mil Reais",
        "resultados": [
            {
                "classificacoes": [],
                "series": [
                    {
                        "localidade": {
                            "id": "2918001",
                            "nivel": {"id": "N6", "nome": "Município"},
                            "nome": "Jequié (BA)",
                        },
                        "serie": {
                            "2020": "2569664",
                            "2021": "3175607",
                            "2023": "3882707",
                        },
                    }
                ],
            }
        ],
    }
]


@pytest.fixture
def ibge_municipio():
    import copy

    return copy.deepcopy(SAMPLE_IBGE_MUNICIPIO)


@pytest.fixture
def ibge_populacao():
    import copy

    return copy.deepcopy(SAMPLE_IBGE_POPULACAO)


@pytest.fixture
def ibge_pib():
    import copy

    return copy.deepcopy(SAMPLE_IBGE_PIB)
