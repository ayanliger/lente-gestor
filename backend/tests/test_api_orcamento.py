"""Testes para as rotas /api/v1/orcamento/* e /api/v1/municipio/*."""

from decimal import Decimal

from app.models.contratacoes import Orgao
from app.models.orcamento import DadosMunicipio, ExecucaoOrcamentaria, IndicadorFiscal

# CNPJ isolado dos dados reais de Jequié.
TEST_CNPJ_API = "99000000333333"


async def _seed_orgao(db) -> Orgao:
    orgao = Orgao(cnpj=TEST_CNPJ_API, razao_social="ORGAO API TESTE", esfera="M", uf="BA")
    db.add(orgao)
    await db.flush()
    return orgao


async def _seed_celula(
    db,
    orgao_id,
    *,
    exercicio: int = 2024,
    periodo: int = 6,
    tipo_relatorio: str = "RREO",
    anexo: str = "RREO-Anexo 02",
    rotulo: str = "Total das Despesas Exceto Intra-Orçamentárias",
    cod_conta: str = "RREO2TotalDespesas",
    coluna: str = "DOTAÇÃO INICIAL",
    conta: str = "Saúde",
    valor: Decimal = Decimal("100.00"),
):
    celula = ExecucaoOrcamentaria(
        orgao_id=orgao_id,
        cod_ibge="2918001",
        exercicio=exercicio,
        periodo=periodo,
        periodicidade="B" if tipo_relatorio == "RREO" else "Q",
        tipo_relatorio=tipo_relatorio,
        anexo=anexo,
        rotulo=rotulo,
        cod_conta=cod_conta,
        coluna=coluna,
        conta=conta,
        valor=valor,
        fonte=f"SICONFI_{tipo_relatorio}",
    )
    db.add(celula)
    await db.flush()
    return celula


# ──────────────────────────────────────────
# /orcamento/execucao
# ──────────────────────────────────────────


class TestExecucao:
    async def test_lista_paginada_filtro_exercicio(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        await _seed_celula(
            db_session,
            orgao.id,
            exercicio=9998,
            conta="ZZZ_TESTE_ANO_UNICO",
        )
        await db_session.flush()

        r = await client.get(
            "/api/v1/orcamento/execucao",
            params={"exercicio": 9998, "tamanho_pagina": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert all(d["exercicio"] == 9998 for d in data["dados"])

    async def test_filtra_tipo_relatorio_e_anexo(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        await _seed_celula(
            db_session,
            orgao.id,
            tipo_relatorio="RGF",
            anexo="RGF-Anexo 06",
            cod_conta="DespesaTotalComPessoalDemonstrativoSimplificado",
            coluna="% SOBRE A RCL AJUSTADA",
            conta="ZZZ_RGF_UNICO",
            valor=Decimal("47.28"),
        )
        await db_session.flush()

        r = await client.get(
            "/api/v1/orcamento/execucao",
            params={
                "tipo_relatorio": "RGF",
                "busca": "ZZZ_RGF_UNICO",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["dados"][0]["tipo_relatorio"] == "RGF"
        assert data["dados"][0]["anexo"] == "RGF-Anexo 06"


# ──────────────────────────────────────────
# /orcamento/resumo-por-funcao
# ──────────────────────────────────────────


class TestResumoFuncao:
    async def test_pivota_dotacao_e_empenhado(self, client, db_session):
        orgao = await _seed_orgao(db_session)

        # Criar duas colunas para a mesma função ZZZ_FUNC_X
        await _seed_celula(
            db_session,
            orgao.id,
            exercicio=9997,
            conta="ZZZ_FUNC_X",
            coluna="DOTAÇÃO INICIAL",
            valor=Decimal("1000"),
        )
        await _seed_celula(
            db_session,
            orgao.id,
            exercicio=9997,
            conta="ZZZ_FUNC_X",
            coluna="DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
            valor=Decimal("800"),
        )
        await db_session.flush()

        r = await client.get(
            "/api/v1/orcamento/resumo-por-funcao",
            params={"exercicio": 9997, "periodo": 6},
        )
        assert r.status_code == 200
        dados = r.json()
        minha = next(d for d in dados if d["funcao"] == "ZZZ_FUNC_X")
        assert minha["dotacao_inicial"] == 1000
        assert minha["empenhado"] == 800

    async def test_exercicio_sem_dados_retorna_vazio(self, client):
        r = await client.get(
            "/api/v1/orcamento/resumo-por-funcao", params={"exercicio": 1900}
        )
        assert r.status_code == 200
        assert r.json() == []


# ──────────────────────────────────────────
# /orcamento/indicadores
# ──────────────────────────────────────────


class TestIndicadores:
    async def test_lista_filtrada_por_situacao(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        ind_ok = IndicadorFiscal(
            orgao_id=orgao.id,
            exercicio=9996,
            periodo=3,
            codigo="DESPESA_PESSOAL_PCT_RCL",
            descricao="teste",
            unidade="PERCENTUAL",
            valor=Decimal("46"),
            limite_legal=Decimal("54"),
            situacao="OK",
            fonte_relatorio="RGF",
            fonte_exercicio=9996,
            fonte_periodo=3,
        )
        ind_alerta = IndicadorFiscal(
            orgao_id=orgao.id,
            exercicio=9996,
            periodo=3,
            codigo="DESPESA_PESSOAL_PRUDENCIAL",
            descricao="teste",
            unidade="PERCENTUAL",
            valor=Decimal("50"),
            limite_legal=Decimal("51.3"),
            situacao="ALERTA",
            fonte_relatorio="RGF",
            fonte_exercicio=9996,
            fonte_periodo=3,
        )
        db_session.add_all([ind_ok, ind_alerta])
        await db_session.flush()

        r = await client.get(
            "/api/v1/orcamento/indicadores",
            params={"exercicio": 9996, "situacao": "ALERTA"},
        )
        assert r.status_code == 200
        dados = r.json()
        assert len(dados) == 1
        assert dados[0]["codigo"] == "DESPESA_PESSOAL_PRUDENCIAL"
        assert dados[0]["situacao"] == "ALERTA"


# ──────────────────────────────────────────
# /municipio/dados
# ──────────────────────────────────────────


class TestMunicipioDados:
    async def test_lista_serie_completa(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        db_session.add_all(
            [
                DadosMunicipio(
                    orgao_id=orgao.id,
                    codigo_ibge="9999999",
                    exercicio=9995,
                    populacao=100000,
                    pib_corrente=Decimal("1000000000"),
                    pib_per_capita=Decimal("10000"),
                    fonte="IBGE",
                    nome_municipio="ZZZ_TESTE",
                    uf="BA",
                ),
                DadosMunicipio(
                    orgao_id=orgao.id,
                    codigo_ibge="9999999",
                    exercicio=9994,
                    populacao=95000,
                    pib_corrente=Decimal("900000000"),
                    pib_per_capita=Decimal("9473"),
                    fonte="IBGE",
                    nome_municipio="ZZZ_TESTE",
                    uf="BA",
                ),
            ]
        )
        await db_session.flush()

        r = await client.get(
            "/api/v1/municipio/dados", params={"exercicio": 9995}
        )
        assert r.status_code == 200
        dados = r.json()
        assert len(dados) == 1
        assert dados[0]["populacao"] == 100000
        assert dados[0]["pib_corrente"] == 1_000_000_000
