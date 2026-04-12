"""Testes para o pipeline de ingestão PNCP."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.contratacoes import Contratacao, Contrato, Fornecedor, Orgao
from app.services.ingestao_pncp import (
    _normalizar_contratacao,
    _normalizar_contrato,
    _parse_date,
    _parse_datetime,
    _upsert_fornecedor,
    _upsert_orgao,
    ingerir_contratacoes,
    ingerir_contratos,
)
from tests.conftest import SAMPLE_CONTRATACAO_RAW, SAMPLE_CONTRATO_RAW


# ──────────────────────────────────────────
# Parsers de data
# ──────────────────────────────────────────


class TestParsers:
    def test_parse_date_iso(self):
        assert _parse_date("2025-04-01") == date(2025, 4, 1)

    def test_parse_date_datetime_string(self):
        assert _parse_date("2025-03-15T10:00:00") == date(2025, 3, 15)

    def test_parse_date_with_timezone(self):
        assert _parse_date("2025-03-15T10:00:00Z") == date(2025, 3, 15)

    def test_parse_date_none(self):
        assert _parse_date(None) is None

    def test_parse_date_empty(self):
        assert _parse_date("") is None

    def test_parse_datetime_iso(self):
        dt = _parse_datetime("2025-03-15T10:30:00")
        assert dt is not None
        assert dt.year == 2025
        assert dt.hour == 10

    def test_parse_datetime_none(self):
        assert _parse_datetime(None) is None


# ──────────────────────────────────────────
# Normalizadores
# ──────────────────────────────────────────


class TestNormalizadores:
    def test_normalizar_contratacao_campos_essenciais(self, contratacao_raw):
        result = _normalizar_contratacao(contratacao_raw)

        assert result["pncp_id"] == contratacao_raw["numeroControlePNCP"]
        assert result["ano"] == 2025
        assert result["numero_sequencial"] == 999
        assert result["numero_processo"] == "TEST-100/2025"
        assert result["modalidade"] == "Pregão - Eletrônico"
        assert "TESTE" in result["objeto"]
        assert result["valor_estimado"] == 150000.00
        assert result["valor_homologado"] == 142000.00
        assert result["situacao"] == "Homologada"
        assert result["data_publicacao"] == date(2025, 3, 15)
        assert result["fonte"] == "pncp"

    def test_normalizar_contratacao_preserva_json_bruto(self, contratacao_raw):
        result = _normalizar_contratacao(contratacao_raw)
        assert "TESTE" in result["dados_brutos"]

    def test_normalizar_contratacao_campos_nulos(self):
        """Campos ausentes devem resultar em None."""
        result = _normalizar_contratacao({"numeroControlePNCP": "test-id"})
        assert result["pncp_id"] == "test-id"
        assert result["ano"] is None
        assert result["valor_estimado"] is None
        assert result["data_publicacao"] is None

    def test_normalizar_contrato_campos_essenciais(self, contrato_raw):
        result = _normalizar_contrato(contrato_raw)

        assert result["pncp_id"] == contrato_raw["numeroControlePNCP"]
        assert result["numero_contrato"] == "CONTRATO N° TEST-001/2025"
        assert result["ano"] == 2025
        assert result["valor_inicial"] == 142000.00
        assert result["valor_atual"] == 142000.00
        assert result["data_assinatura"] == date(2025, 4, 1)
        assert result["data_fim_vigencia"] == date(2026, 4, 1)
        assert result["categoria"] == "Compras"
        assert result["fonte"] == "pncp"

    def test_normalizar_contrato_categoria_nula(self):
        result = _normalizar_contrato({"categoriaProcesso": None})
        assert result["categoria"] is None


# ──────────────────────────────────────────
# Upserts (contra DB real)
# ──────────────────────────────────────────


class TestUpserts:
    async def test_upsert_orgao_cria_novo(self, db_session):
        orgao = await _upsert_orgao(db_session, {
            "cnpj": "99999999000100",
            "razaoSocial": "TESTE ORGAO",
            "esferaId": "M",
        })
        assert orgao.id is not None
        assert orgao.cnpj == "99999999000100"
        assert orgao.razao_social == "TESTE ORGAO"

    async def test_upsert_orgao_retorna_existente(self, db_session):
        orgao1 = await _upsert_orgao(db_session, {
            "cnpj": "99999999000100",
            "razaoSocial": "TESTE ORGAO",
        })
        orgao2 = await _upsert_orgao(db_session, {
            "cnpj": "99999999000100",
            "razaoSocial": "NOME DIFERENTE",
        })
        assert orgao1.id == orgao2.id

    async def test_upsert_fornecedor_cria_novo(self, db_session):
        fornecedor = await _upsert_fornecedor(db_session, {
            "cpf_cnpj": "11111111000100",
            "nome": "EMPRESA TESTE",
            "tipo": "PJ",
        })
        assert fornecedor.id is not None
        assert fornecedor.nome == "EMPRESA TESTE"

    async def test_upsert_fornecedor_retorna_existente(self, db_session):
        f1 = await _upsert_fornecedor(db_session, {
            "cpf_cnpj": "11111111000100",
            "nome": "EMPRESA TESTE",
        })
        f2 = await _upsert_fornecedor(db_session, {
            "cpf_cnpj": "11111111000100",
            "nome": "OUTRO NOME",
        })
        assert f1.id == f2.id


# ──────────────────────────────────────────
# Pipeline completa (mock da API)
# ──────────────────────────────────────────


class TestPipelineContratacoes:
    @patch("app.services.ingestao_pncp.PNCPClient")
    @patch("app.services.ingestao_pncp.async_session")
    async def test_ingerir_contratacoes_cria_registros(
        self, mock_session_factory, mock_client_cls, db_session
    ):
        """Pipeline completa: mock API → normalização → persistência."""
        # Mock do PNCPClient
        mock_pncp = AsyncMock()
        mock_pncp.paginar_todos.return_value = [SAMPLE_CONTRATACAO_RAW]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_pncp)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock da sessão para usar a do teste
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_contratacoes(
            date(2025, 1, 1), date(2025, 6, 1), modalidades=[8]
        )

        assert stats["criadas"] == 1
        assert stats["erros"] == 0

        # Verificar no banco (filtrar por dados de teste)
        result = await db_session.execute(
            select(Contratacao).where(Contratacao.pncp_id == SAMPLE_CONTRATACAO_RAW["numeroControlePNCP"])
        )
        contratacoes = result.scalars().all()
        assert len(contratacoes) >= 1
        assert contratacoes[0].pncp_id == f"{SAMPLE_CONTRATACAO_RAW['orgaoEntidade']['cnpj']}-1-000999/2025"
        assert "TESTE" in contratacoes[0].objeto

        # Órgão criado
        result = await db_session.execute(
            select(Orgao).where(Orgao.cnpj == SAMPLE_CONTRATACAO_RAW["orgaoEntidade"]["cnpj"])
        )
        assert result.scalars().first() is not None

    @patch("app.services.ingestao_pncp.PNCPClient")
    @patch("app.services.ingestao_pncp.async_session")
    async def test_ingerir_contratacoes_upsert_atualiza(
        self, mock_session_factory, mock_client_cls, db_session
    ):
        """Re-ingestão atualiza registros existentes em vez de duplicar."""
        mock_pncp = AsyncMock()
        mock_pncp.paginar_todos.return_value = [SAMPLE_CONTRATACAO_RAW]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_pncp)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Primeira ingestão
        stats1 = await ingerir_contratacoes(date(2025, 1, 1), date(2025, 6, 1), modalidades=[8])
        assert stats1["criadas"] == 1

        # Segunda ingestão — mesmo dado
        stats2 = await ingerir_contratacoes(date(2025, 1, 1), date(2025, 6, 1), modalidades=[8])
        assert stats2["atualizadas"] == 1
        assert stats2["criadas"] == 0

        # Sem duplicatas para o registro de teste
        result = await db_session.execute(
            select(Contratacao).where(Contratacao.pncp_id == SAMPLE_CONTRATACAO_RAW["numeroControlePNCP"])
        )
        assert len(result.scalars().all()) == 1

    @patch("app.services.ingestao_pncp.PNCPClient")
    async def test_ingerir_contratacoes_fetch_erro_continua(self, mock_client_cls):
        """Erro em uma modalidade não interrompe as demais."""
        mock_pncp = AsyncMock()
        mock_pncp.paginar_todos.side_effect = Exception("API timeout")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_pncp)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_contratacoes(
            date(2025, 1, 1), date(2025, 6, 1), modalidades=[4, 5]
        )

        assert stats["erros"] == 2
        assert stats["criadas"] == 0


class TestPipelineContratos:
    @patch("app.services.ingestao_pncp.PNCPClient")
    @patch("app.services.ingestao_pncp.async_session")
    async def test_ingerir_contratos_cria_registros(
        self, mock_session_factory, mock_client_cls, db_session
    ):
        """Pipeline de contratos: cria contrato, órgão e fornecedor."""
        mock_pncp = AsyncMock()
        mock_pncp.paginar_todos.return_value = [SAMPLE_CONTRATO_RAW]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_pncp)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_contratos(date(2025, 1, 1), date(2025, 6, 1))

        assert stats["criados"] == 1
        assert stats["erros"] == 0

        # Contrato de teste
        result = await db_session.execute(
            select(Contrato).where(Contrato.pncp_id == SAMPLE_CONTRATO_RAW["numeroControlePNCP"])
        )
        contratos = result.scalars().all()
        assert len(contratos) >= 1
        assert contratos[0].valor_inicial == 142000.00
        assert contratos[0].data_fim_vigencia == date(2026, 4, 1)

        # Fornecedor de teste criado
        result = await db_session.execute(
            select(Fornecedor).where(Fornecedor.cpf_cnpj == SAMPLE_CONTRATO_RAW["niFornecedor"])
        )
        f = result.scalars().first()
        assert f is not None
        assert f.nome == "EMPRESA TESTE LTDA"

    @patch("app.services.ingestao_pncp.PNCPClient")
    async def test_ingerir_contratos_fetch_erro(self, mock_client_cls):
        """Erro no fetch retorna stats zerados sem crash."""
        mock_pncp = AsyncMock()
        mock_pncp.paginar_todos.side_effect = Exception("Connection refused")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_pncp)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_contratos(date(2025, 1, 1), date(2025, 6, 1))

        assert stats["criados"] == 0
        assert stats["atualizados"] == 0
