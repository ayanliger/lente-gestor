"""Testes para o pipeline de ingestão do RREO (SICONFI)."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.contratacoes import Orgao
from app.models.orcamento import ExecucaoOrcamentaria
from app.services.ingestao_orcamento import (
    FONTE_RREO,
    TIPO_RELATORIO_RREO,
    _normalizar_rreo,
    _parse_decimal,
    _upsert_orgao_from_siconfi,
    ingerir_rreo,
)

# ──────────────────────────────────────────
# Parsers
# ──────────────────────────────────────────


class TestParseDecimal:
    def test_parse_decimal_numero(self):
        assert _parse_decimal(125430789.15) == Decimal("125430789.15")

    def test_parse_decimal_string(self):
        assert _parse_decimal("1000") == Decimal("1000")

    def test_parse_decimal_none(self):
        assert _parse_decimal(None) is None

    def test_parse_decimal_vazio(self):
        assert _parse_decimal("") is None

    def test_parse_decimal_invalido(self):
        assert _parse_decimal("abc") is None


# ──────────────────────────────────────────
# Normalizador
# ──────────────────────────────────────────


class TestNormalizadorRREO:
    def test_normalizar_rreo_campos_essenciais(self, rreo_item):
        result = _normalizar_rreo(rreo_item)

        assert result["exercicio"] == 2024
        assert result["periodo"] == 6
        assert result["periodicidade"] == "B"
        assert result["tipo_relatorio"] == TIPO_RELATORIO_RREO
        assert result["anexo"] == "RREO-Anexo 02"
        assert result["rotulo"] == "Total das Despesas Exceto Intra-Orçamentárias"
        assert result["coluna"] == "DOTAÇÃO INICIAL"
        assert result["cod_conta"] == "RREO2TotalDespesas"
        assert result["conta"] == "Saúde"
        assert result["valor"] == Decimal("125430789.15")
        assert result["cod_ibge"] == "2918001"
        assert result["fonte"] == FONTE_RREO

    def test_normalizar_rreo_preserva_json_bruto(self, rreo_item):
        result = _normalizar_rreo(rreo_item)
        assert "RREO2TotalDespesas" in result["dados_brutos"]
        assert "Saúde" in result["dados_brutos"]

    def test_normalizar_rreo_valor_nulo(self, rreo_item):
        rreo_item["valor"] = None
        result = _normalizar_rreo(rreo_item)
        assert result["valor"] is None


# ──────────────────────────────────────────
# Upsert de órgão via SICONFI
# ──────────────────────────────────────────


# CNPJ fake isolado dos dados reais de Jequié (que podem estar no DB
# por conta de ingestões PNCP anteriores).
TEST_CNPJ_SICONFI = "99000000777777"


class TestUpsertsOrcamento:
    async def test_upsert_orgao_cria_novo_com_municipio(
        self, db_session, rreo_item, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_orcamento.settings.pncp_cnpj_jequie",
            TEST_CNPJ_SICONFI,
        )

        orgao = await _upsert_orgao_from_siconfi(db_session, rreo_item)
        assert orgao.id is not None
        assert orgao.cnpj == TEST_CNPJ_SICONFI
        assert orgao.uf == "BA"
        assert orgao.esfera == "M"
        assert orgao.municipio == "Jequié"
        assert "Jequié" in orgao.razao_social

    async def test_upsert_orgao_reusa_existente_e_enriquece(
        self, db_session, rreo_item, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_orcamento.settings.pncp_cnpj_jequie",
            TEST_CNPJ_SICONFI,
        )

        # Pré-semear um órgão com o mesmo CNPJ sem UF/município.
        pre = Orgao(cnpj=TEST_CNPJ_SICONFI, razao_social="EXISTENTE")
        db_session.add(pre)
        await db_session.flush()
        pre_id = pre.id

        orgao = await _upsert_orgao_from_siconfi(db_session, rreo_item)
        # Reutiliza o mesmo registro e enriquece UF/município/esfera.
        assert orgao.id == pre_id
        assert orgao.uf == "BA"
        assert orgao.municipio == "Jequié"
        assert orgao.esfera == "M"


# ──────────────────────────────────────────
# Pipeline completa (API mockada)
# ──────────────────────────────────────────


class TestPipelineRREO:
    @patch("app.services.ingestao_orcamento.SICONFIClient")
    @patch("app.services.ingestao_orcamento.async_session")
    async def test_ingerir_rreo_cria_registros(
        self, mock_session_factory, mock_client_cls, db_session, rreo_item, monkeypatch
    ):
        """Pipeline: mock API → normalização → persistência."""
        monkeypatch.setattr(
            "app.services.ingestao_orcamento.settings.pncp_cnpj_jequie",
            TEST_CNPJ_SICONFI,
        )
        mock_siconfi = AsyncMock()
        mock_siconfi.paginar_rreo.return_value = [rreo_item]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_siconfi)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_rreo(exercicio=2024, periodos=[6])

        assert stats["criados"] == 1
        assert stats["erros"] == 0
        assert stats["periodos_processados"] == 1

        # Filtrar pelo órgão de teste (isolado do CNPJ real de Jequié).
        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_SICONFI)
        )
        test_orgao_id = orgao_res.scalar_one()

        result = await db_session.execute(
            select(ExecucaoOrcamentaria).where(
                ExecucaoOrcamentaria.orgao_id == test_orgao_id,
                ExecucaoOrcamentaria.cod_conta == rreo_item["cod_conta"],
                ExecucaoOrcamentaria.coluna == rreo_item["coluna"],
                ExecucaoOrcamentaria.conta == rreo_item["conta"],
                ExecucaoOrcamentaria.exercicio == 2024,
                ExecucaoOrcamentaria.periodo == 6,
            )
        )
        registros = result.scalars().all()
        assert len(registros) == 1
        assert registros[0].valor == Decimal("125430789.15")
        assert registros[0].fonte == FONTE_RREO
        assert registros[0].cod_ibge == "2918001"

    @patch("app.services.ingestao_orcamento.SICONFIClient")
    @patch("app.services.ingestao_orcamento.async_session")
    async def test_ingerir_rreo_upsert_atualiza(
        self, mock_session_factory, mock_client_cls, db_session, rreo_item, monkeypatch
    ):
        """Re-ingestão atualiza em vez de duplicar."""
        monkeypatch.setattr(
            "app.services.ingestao_orcamento.settings.pncp_cnpj_jequie",
            TEST_CNPJ_SICONFI,
        )
        mock_siconfi = AsyncMock()
        mock_siconfi.paginar_rreo.return_value = [rreo_item]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_siconfi)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats1 = await ingerir_rreo(exercicio=2024, periodos=[6])
        assert stats1["criados"] == 1

        # Segunda ingestão com valor diferente
        rreo_item_atualizado = rreo_item.copy()
        rreo_item_atualizado["valor"] = 999999.99
        mock_siconfi.paginar_rreo.return_value = [rreo_item_atualizado]

        stats2 = await ingerir_rreo(exercicio=2024, periodos=[6])
        assert stats2["atualizados"] == 1
        assert stats2["criados"] == 0

        # Verificar que o valor foi atualizado e não há duplicata.
        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_SICONFI)
        )
        test_orgao_id = orgao_res.scalar_one()

        result = await db_session.execute(
            select(ExecucaoOrcamentaria).where(
                ExecucaoOrcamentaria.orgao_id == test_orgao_id,
                ExecucaoOrcamentaria.cod_conta == rreo_item["cod_conta"],
                ExecucaoOrcamentaria.coluna == rreo_item["coluna"],
                ExecucaoOrcamentaria.conta == rreo_item["conta"],
                ExecucaoOrcamentaria.exercicio == 2024,
                ExecucaoOrcamentaria.periodo == 6,
            )
        )
        registros = result.scalars().all()
        assert len(registros) == 1
        assert registros[0].valor == Decimal("999999.99")

    @patch("app.services.ingestao_orcamento.SICONFIClient")
    async def test_ingerir_rreo_fetch_erro_continua(self, mock_client_cls):
        """Erro no fetch de um período não interrompe os demais."""
        mock_siconfi = AsyncMock()
        mock_siconfi.paginar_rreo.side_effect = Exception("API timeout")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_siconfi)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_rreo(exercicio=2024, periodos=[5, 6])

        # Dois períodos falharam mas a função não explodiu
        assert stats["erros"] == 2
        assert stats["criados"] == 0
        assert stats["periodos_processados"] == 0

    @patch("app.services.ingestao_orcamento.SICONFIClient")
    @patch("app.services.ingestao_orcamento.async_session")
    async def test_ingerir_rreo_ignora_item_incompleto(
        self, mock_session_factory, mock_client_cls, db_session, rreo_item, monkeypatch
    ):
        """Item sem cod_conta/anexo é logado e ignorado, sem contar como erro."""
        monkeypatch.setattr(
            "app.services.ingestao_orcamento.settings.pncp_cnpj_jequie",
            TEST_CNPJ_SICONFI,
        )
        incompleto = {**rreo_item, "cod_conta": None}
        mock_siconfi = AsyncMock()
        mock_siconfi.paginar_rreo.return_value = [incompleto, rreo_item]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_siconfi)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_rreo(exercicio=2024, periodos=[6])

        # 1 registro válido criado, 0 erros (item incompleto foi só warning)
        assert stats["criados"] == 1
        assert stats["erros"] == 0
