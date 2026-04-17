"""Testes para o pipeline de ingestão do IBGE."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.contratacoes import Orgao
from app.models.orcamento import DadosMunicipio
from app.services.ingestao_ibge import (
    FATOR_MIL_REAIS,
    FONTE_IBGE,
    _extrair_serie,
    _extrair_uf_nome,
    _upsert_orgao_from_ibge,
    ingerir_ibge,
)

# CNPJ fake para isolar do órgão real de Jequié inserido pela Fase 1.
TEST_CNPJ_IBGE = "99000000888888"
TEST_CODIGO_IBGE = "2918001"


# ──────────────────────────────────────────
# Extratores
# ──────────────────────────────────────────


class TestExtrairSerie:
    def test_extrair_serie_valida(self, ibge_populacao):
        serie = _extrair_serie(ibge_populacao)
        assert serie[2020] == "156126"
        assert serie[2024] == "168733"
        assert 2021 in serie

    def test_extrair_serie_payload_vazio(self):
        assert _extrair_serie([]) == {}

    def test_extrair_serie_sem_resultados(self):
        assert _extrair_serie([{"id": "x", "resultados": []}]) == {}

    def test_extrair_serie_malformado(self):
        assert _extrair_serie([{"unexpected": "shape"}]) == {}


class TestExtrairUFNome:
    def test_extrair_uf_nome(self, ibge_municipio):
        uf, nome = _extrair_uf_nome(ibge_municipio)
        assert uf == "BA"
        assert nome == "Jequié"

    def test_extrair_uf_nome_sem_metadata(self):
        uf, nome = _extrair_uf_nome({})
        assert uf is None
        assert nome is None


# ──────────────────────────────────────────
# Upsert de órgão via IBGE
# ──────────────────────────────────────────


class TestUpsertOrgaoIBGE:
    async def test_upsert_orgao_cria_novo(
        self, db_session, ibge_municipio, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_ibge.settings.pncp_cnpj_jequie",
            TEST_CNPJ_IBGE,
        )
        orgao = await _upsert_orgao_from_ibge(db_session, ibge_municipio)
        assert orgao.id is not None
        assert orgao.cnpj == TEST_CNPJ_IBGE
        assert orgao.uf == "BA"
        assert orgao.municipio == "Jequié"
        assert orgao.esfera == "M"

    async def test_upsert_orgao_reusa_existente_e_enriquece(
        self, db_session, ibge_municipio, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_ibge.settings.pncp_cnpj_jequie",
            TEST_CNPJ_IBGE,
        )
        pre = Orgao(cnpj=TEST_CNPJ_IBGE, razao_social="PRE-EXISTENTE")
        db_session.add(pre)
        await db_session.flush()
        pre_id = pre.id

        orgao = await _upsert_orgao_from_ibge(db_session, ibge_municipio)
        assert orgao.id == pre_id
        assert orgao.uf == "BA"
        assert orgao.municipio == "Jequié"


# ──────────────────────────────────────────
# Pipeline completa (APIs mockadas)
# ──────────────────────────────────────────


class TestPipelineIBGE:
    @patch("app.services.ingestao_ibge.IBGEClient")
    @patch("app.services.ingestao_ibge.async_session")
    async def test_ingerir_ibge_cria_registros_com_pib_per_capita(
        self,
        mock_session_factory,
        mock_client_cls,
        db_session,
        ibge_municipio,
        ibge_populacao,
        ibge_pib,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.ingestao_ibge.settings.pncp_cnpj_jequie",
            TEST_CNPJ_IBGE,
        )

        mock_ibge = AsyncMock()
        mock_ibge.municipio.return_value = ibge_municipio
        mock_ibge.populacao.return_value = ibge_populacao
        mock_ibge.pib.return_value = ibge_pib
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ibge)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_ibge(codigo_ibge=TEST_CODIGO_IBGE)

        # Fixtures têm anos 2020, 2021, 2023, 2024 combinados entre população e PIB.
        assert stats["criados"] == 4
        assert stats["erros"] == 0

        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_IBGE)
        )
        test_orgao_id = orgao_res.scalar_one()

        result = await db_session.execute(
            select(DadosMunicipio)
            .where(DadosMunicipio.orgao_id == test_orgao_id)
            .order_by(DadosMunicipio.exercicio)
        )
        registros = result.scalars().all()
        assert len(registros) == 4

        por_ano = {r.exercicio: r for r in registros}

        # 2020 tem ambos: PIB (2.569.664 mil) * 1000 = 2.569.664.000 reais
        r2020 = por_ano[2020]
        assert r2020.populacao == 156126
        assert r2020.pib_corrente == Decimal("2569664") * FATOR_MIL_REAIS
        assert r2020.pib_per_capita == (
            Decimal("2569664000") / Decimal(156126)
        ).quantize(Decimal("0.01"))
        assert r2020.fonte == FONTE_IBGE
        assert r2020.codigo_ibge == TEST_CODIGO_IBGE
        assert r2020.uf == "BA"
        assert r2020.nome_municipio == "Jequié"

        # 2023 tem PIB mas não população -> sem per capita
        r2023 = por_ano[2023]
        assert r2023.pib_corrente == Decimal("3882707") * FATOR_MIL_REAIS
        assert r2023.populacao is None
        assert r2023.pib_per_capita is None

        # 2024 tem população mas não PIB -> sem per capita
        r2024 = por_ano[2024]
        assert r2024.populacao == 168733
        assert r2024.pib_corrente is None
        assert r2024.pib_per_capita is None

    @patch("app.services.ingestao_ibge.IBGEClient")
    @patch("app.services.ingestao_ibge.async_session")
    async def test_ingerir_ibge_reingestao_atualiza(
        self,
        mock_session_factory,
        mock_client_cls,
        db_session,
        ibge_municipio,
        ibge_populacao,
        ibge_pib,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.ingestao_ibge.settings.pncp_cnpj_jequie",
            TEST_CNPJ_IBGE,
        )

        mock_ibge = AsyncMock()
        mock_ibge.municipio.return_value = ibge_municipio
        mock_ibge.populacao.return_value = ibge_populacao
        mock_ibge.pib.return_value = ibge_pib
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ibge)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats1 = await ingerir_ibge(codigo_ibge=TEST_CODIGO_IBGE)
        assert stats1["criados"] == 4

        # Mudar PIB de 2020 e reingerir
        ibge_pib_alterado = [dict(ibge_pib[0])]
        ibge_pib_alterado[0]["resultados"] = [
            {
                "classificacoes": [],
                "series": [
                    {
                        "localidade": ibge_pib[0]["resultados"][0]["series"][0][
                            "localidade"
                        ],
                        "serie": {"2020": "9999999"},
                    }
                ],
            }
        ]
        mock_ibge.pib.return_value = ibge_pib_alterado

        stats2 = await ingerir_ibge(codigo_ibge=TEST_CODIGO_IBGE)
        # Só 2020 volta no payload de PIB, e agora 2021/2023/2024 saem de PIB mas
        # 2024/2021 continuam no payload de população -> ainda devem ser atualizados.
        assert stats2["atualizados"] >= 1

        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_IBGE)
        )
        test_orgao_id = orgao_res.scalar_one()

        result = await db_session.execute(
            select(DadosMunicipio).where(
                DadosMunicipio.orgao_id == test_orgao_id,
                DadosMunicipio.exercicio == 2020,
            )
        )
        r2020 = result.scalar_one()
        assert r2020.pib_corrente == Decimal("9999999") * FATOR_MIL_REAIS

    @patch("app.services.ingestao_ibge.IBGEClient")
    async def test_ingerir_ibge_falha_metadata_aborta(self, mock_client_cls):
        """Se `municipio` falha, a ingestão não prossegue para séries."""
        mock_ibge = AsyncMock()
        mock_ibge.municipio.side_effect = Exception("IBGE fora do ar")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ibge)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_ibge(codigo_ibge=TEST_CODIGO_IBGE)

        assert stats["erros"] == 1
        assert stats["criados"] == 0
        assert stats["atualizados"] == 0
        # Nem chegou a chamar populacao/pib
        mock_ibge.populacao.assert_not_called()
        mock_ibge.pib.assert_not_called()
