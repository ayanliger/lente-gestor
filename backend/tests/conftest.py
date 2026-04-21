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


# ────────────────────────────────────────
# Fixtures: payloads RGF simulados
# ────────────────────────────────────────

# Capturado de /tt/rgf?an_exercicio=2024&nr_periodo=2&id_ente=2918001&co_tipo_demonstrativo=RGF
#  &co_esfera=M&co_poder=E&in_periodicidade=Q (Jequié Q2/2024, Anexo 06).
SAMPLE_RGF_ITEM = {
    "exercicio": 2024,
    "periodo": 2,
    "periodicidade": "Q",
    "instituicao": "Prefeitura Municipal de Jequié - BA",
    "cod_ibge": 2918001,
    "uf": "BA",
    "co_poder": "E",
    "populacao": 156408,
    "anexo": "RGF-Anexo 06",
    "esfera": "M",
    "rotulo": "Padrão",
    "coluna": "% SOBRE A RCL AJUSTADA",
    "cod_conta": "DespesaTotalComPessoalDemonstrativoSimplificado",
    "conta": "Despesa Total com Pessoal - DTP",
    "valor": 47.28,
}


@pytest.fixture
def rgf_item():
    return SAMPLE_RGF_ITEM.copy()


# ─────────────────────────────────────
# Fixtures: Município Online (arrecadação)
# ─────────────────────────────────────

# HTML capturado da resposta agregada do portal (reduzido: 2 itens de receita).
# Estrutura observada via inspeção do DOM real do
# `municipioonline.com.br/ba/prefeitura/jequie/cidadao/receita`.
_DATA_KEY_IPTU = (
    '{"NuCnpj": "13894878000160", "DtAno": "2026", '
    '"DtAnoMes": "202602", "DtPeriodo": "", '
    '"FlCovid19": "0", "CdItemReceita": "111250010000"}'
)
_DATA_KEY_TFF = (
    '{"NuCnpj": "13894878000160", "DtAno": "2026", '
    '"DtAnoMes": "202602", "DtPeriodo": "", '
    '"FlCovid19": "0", "CdItemReceita": "112101010200"}'
)
SAMPLE_MUNICIPIO_ONLINE_HTML = f"""
<html><body>
<table>
  <thead><tr>
    <th></th><th>Poder</th><th>Órgão</th><th>Categoria</th><th>Receita</th>
    <th>Descrição</th><th>Data</th><th>Previsto</th><th>Atualizado</th>
    <th>Período</th><th>Acumulado</th><th>%</th><th>NuCnpj</th>
  </tr></thead>
  <tbody>
    <tr data-key='{_DATA_KEY_IPTU}'>
      <td width="6px"></td>
      <td>Executivo</td>
      <td>PREFEITURA MUNICIPAL DE JEQUIE</td>
      <td>Obrigatória</td>
      <td>111250010000</td>
      <td>Imposto sobre a Propriedade Predial e Territorial Urbana - Principal</td>
      <td>11/02/2026</td>
      <td>R$ 10.000.000,00</td>
      <td>R$ 10.000.000,00</td>
      <td>R$ 32.813,40</td>
      <td>R$ 270.631,73</td>
      <td>2.70</td>
      <td>13894878000160</td>
    </tr>
    <tr>
      <td style="display: none"></td>
      <td style="display: none"></td>
      <td style="display: none"></td>
      <td style="display: none"></td>
      <td style="display: none"></td>
      <td style="display: none"></td>
      <td style="display: none"></td>
      <td colspan="7">15001001 - Recurso não Vinculado de Imposto destinado à Educação<br/></td>
      <td align="right">R$ 2.500.000,00<br/></td>
      <td align="right">R$ 2.500.000,00<br/></td>
      <td align="right">R$ 8.203,36<br/></td>
      <td align="right">R$ 67.657,87<br/></td>
      <td align="center"></td>
    </tr>
    <tr data-key='{_DATA_KEY_TFF}'>
      <td width="6px"></td>
      <td>Executivo</td>
      <td>PREFEITURA MUNICIPAL DE JEQUIE</td>
      <td>Obrigatória</td>
      <td>112101010200</td>
      <td>Taxa de Fiscalização e Funcionamento - TFF - Principal</td>
      <td>11/02/2026</td>
      <td>R$ 8.200.000,00</td>
      <td>R$ 8.200.000,00</td>
      <td>R$ 309.457,54</td>
      <td>R$ 1.190.972,68</td>
      <td>14.52</td>
      <td>13894878000160</td>
    </tr>
  </tbody>
</table>
</body></html>
"""

# HTML do drill-down (campo `DsReceitaDetalhe` da resposta JSON).
# Classes CSS vem do template `ReceitaDetalhe.htm` usado pelo Receita.js.
SAMPLE_DRILL_DOWN_HTML = """
<table>
  <tr>
    <td class="dt_emissao">05/02/2026</td>
    <td class="nu_processo">2026/00123</td>
    <td class="ds_contaBanco">BANCO DO BRASIL S.A.</td>
    <td class="vl_realizado">R$ 15.000,00</td>
    <td class="ds_observacao">IPTU cota única</td>
  </tr>
  <tr>
    <td class="dt_emissao">12/02/2026</td>
    <td class="nu_processo">2026/00124</td>
    <td class="ds_contaBanco">CAIXA ECONOMICA FEDERAL</td>
    <td class="vl_realizado">R$ 17.813,40</td>
    <td class="ds_observacao">IPTU parcelado</td>
  </tr>
</table>
"""

# Estrutura normalizada retornada por `listar_receitas` para o HTML acima.
SAMPLE_MUNICIPIO_ONLINE_REGISTROS = [
    {
        "keys": {
            "NuCnpj": "13894878000160",
            "DtAno": "2026",
            "DtAnoMes": "202602",
            "DtPeriodo": "",
            "FlCovid19": "0",
            "CdItemReceita": "111250010000",
        },
        "poder": "Executivo",
        "orgao": "PREFEITURA MUNICIPAL DE JEQUIE",
        "categoria": "Obrigatória",
        "cod_item_receita": "111250010000",
        "descricao_receita": "Imposto sobre a Propriedade Predial e Territorial Urbana - Principal",
        "data_emissao": "11/02/2026",
        "valor_previsto": "R$ 10.000.000,00",
        "valor_atualizado": "R$ 10.000.000,00",
        "valor_arrecadado_periodo": "R$ 32.813,40",
        "valor_arrecadado_acumulado": "R$ 270.631,73",
        "valor_previsto_total": "R$ 10.000.000,00",
        "valor_atualizado_total": "R$ 10.000.000,00",
        "valor_arrecadado_periodo_total": "R$ 32.813,40",
        "valor_arrecadado_acumulado_total": "R$ 270.631,73",
        "cod_fonte_recurso": None,
        "descricao_fonte_recurso": None,
    },
]


@pytest.fixture
def municipio_online_html():
    return SAMPLE_MUNICIPIO_ONLINE_HTML


@pytest.fixture
def drill_down_html():
    return SAMPLE_DRILL_DOWN_HTML


@pytest.fixture
def arrecadacao_raw():
    import copy

    return copy.deepcopy(SAMPLE_MUNICIPIO_ONLINE_REGISTROS[0])
