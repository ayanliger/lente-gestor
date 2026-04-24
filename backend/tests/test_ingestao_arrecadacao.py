"""Testes para ingestão de arrecadação (Município Online)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.connectors.municipio_online import (
    _parse_drill_down_html,
    _parse_receitas_html,
)
from app.models.arrecadacao import Arrecadacao, RecolhimentoDetalhe
from app.models.contratacoes import Orgao
from app.services.ingestao_arrecadacao import (
    FONTE_MUNICIPIO_ONLINE,
    _classificar_especie,
    _normalizar_agregado,
    _normalizar_recolhimento,
    _parse_data_br,
    _parse_decimal,
    _upsert_orgao_from_municipio_online,
    ingerir_arrecadacao,
)

# CNPJ de teste — isolado dos dados reais ingeridos pelas outras fontes.
TEST_CNPJ_ARRECADACAO = "99000000666666"


# ──────────────────────────────────────────
# Parsers puros (HTML)
# ──────────────────────────────────────────


class TestParseReceitasHtml:
    def test_extrai_duas_linhas_com_data_key(self, municipio_online_html):
        registros = _parse_receitas_html(municipio_online_html)
        assert len(registros) == 2

    def test_campos_essenciais_preservados(self, municipio_online_html):
        registros = _parse_receitas_html(municipio_online_html)
        # TFF não tem fontes de recursos: a linha emitida tem valores do total.
        tff = next(r for r in registros if r["cod_item_receita"] == "112101010200")
        assert tff["keys"]["CdItemReceita"] == "112101010200"
        assert tff["poder"] == "Executivo"
        assert tff["categoria"] == "Obrigatória"
        assert "TFF" in tff["descricao_receita"] or "Taxa" in tff["descricao_receita"]
        assert tff["valor_arrecadado_periodo"] == "R$ 309.457,54"
        assert tff["valor_arrecadado_acumulado"] == "R$ 1.190.972,68"

    def test_item_sem_fonte_emite_linha_agregada(self, municipio_online_html):
        """TFF não tem sub-linha de fontes → emitida com cod_fonte=None."""
        registros = _parse_receitas_html(municipio_online_html)
        tff = next(r for r in registros if r["cod_item_receita"] == "112101010200")
        assert tff["cod_fonte_recurso"] is None
        assert tff["descricao_fonte_recurso"] is None

    def test_item_com_fonte_emite_linha_por_fonte(self, municipio_online_html):
        """IPTU tem uma sub-linha (fonte 15001001) → emitida com fonte preenchida."""
        registros = _parse_receitas_html(municipio_online_html)
        iptu_fontes = [
            r for r in registros if r["cod_item_receita"] == "111250010000"
        ]
        assert len(iptu_fontes) == 1
        fonte = iptu_fontes[0]
        assert fonte["cod_fonte_recurso"] == "15001001"
        assert "Educação" in fonte["descricao_fonte_recurso"]
        assert fonte["valor_arrecadado_periodo"] == "R$ 8.203,36"

    def test_html_vazio_retorna_lista_vazia(self):
        assert _parse_receitas_html("<html></html>") == []


class TestParseDrillDownHtml:
    def test_extrai_dois_recolhimentos(self, drill_down_html):
        recolhimentos = _parse_drill_down_html(drill_down_html)
        assert len(recolhimentos) == 2

    def test_captura_banco_corretamente(self, drill_down_html):
        recolhimentos = _parse_drill_down_html(drill_down_html)
        bancos = {r["DsContaBanco"] for r in recolhimentos}
        assert "BANCO DO BRASIL S.A." in bancos
        assert "CAIXA ECONOMICA FEDERAL" in bancos

    def test_captura_valor_e_data(self, drill_down_html):
        recolhimentos = _parse_drill_down_html(drill_down_html)
        bb = next(r for r in recolhimentos if "BANCO DO BRASIL" in r["DsContaBanco"])
        assert bb["DtEmissao"] == "05/02/2026"
        assert bb["VlRecolhimento"] == "R$ 15.000,00"


# ──────────────────────────────────────────
# Parsers de valor
# ──────────────────────────────────────────


class TestParseDecimal:
    def test_numero_simples(self):
        assert _parse_decimal(32813.40) == Decimal("32813.4")

    def test_formato_brasileiro_com_prefixo(self):
        assert _parse_decimal("R$ 1.234.567,89") == Decimal("1234567.89")

    def test_formato_sem_prefixo(self):
        assert _parse_decimal("2.500.000,00") == Decimal("2500000.00")

    def test_virgula_sem_milhar(self):
        assert _parse_decimal("10,50") == Decimal("10.50")

    def test_none_e_vazio(self):
        assert _parse_decimal(None) is None
        assert _parse_decimal("") is None
        assert _parse_decimal("   ") is None

    def test_invalido(self):
        assert _parse_decimal("abc") is None


class TestParseDataBR:
    def test_formato_padrao(self):
        assert _parse_data_br("11/02/2026") == date(2026, 2, 11)

    def test_iso(self):
        assert _parse_data_br("2026-02-11") == date(2026, 2, 11)

    def test_none(self):
        assert _parse_data_br(None) is None

    def test_invalido(self):
        assert _parse_data_br("qualquer coisa") is None


# ──────────────────────────────────────────
# Classificação de espécie
# ──────────────────────────────────────────


class TestClassificarEspecie:
    @pytest.mark.parametrize(
        "cod,esperado",
        [
            ("111250010000", "Impostos"),  # IPTU Principal
            ("111451110100", "Impostos"),  # ISSQN Arrecadação Direta
            ("112101010200", "Taxas"),  # TFF Principal
            ("113100000000", "Contribuição de Melhoria"),
            ("121501110100", "Contribuições"),
            ("131210010000", "Patrimonial"),
            ("141200000000", "Agropecuária"),
            ("151000000000", "Industrial"),
            ("161010000000", "Serviços"),
            ("171100000000", "Transferências"),
            ("191990010200", "Não Tributária"),
            ("220000000000", "Capital"),
            ("721551110000", "Intraorçamentária"),  # Contribuição Patronal
            ("810000000000", "Intraorçamentária"),
            ("", "Outras"),
            (None, "Outras"),
        ],
    )
    def test_prefixos(self, cod, esperado):
        assert _classificar_especie(cod) == esperado


# ──────────────────────────────────────────
# Normalizadores
# ──────────────────────────────────────────


class TestNormalizarAgregado:
    def test_campos_principais(self, arrecadacao_raw):
        campos = _normalizar_agregado(arrecadacao_raw, 2026, 2)
        assert campos["exercicio"] == 2026
        assert campos["mes"] == 2

    def test_usa_dt_ano_mes_autoritativo(self, arrecadacao_raw):
        """
        Se o portal ignora o filtro e devolve DtAnoMes=202601 quando pedimos
        mes=2, confiamos no portal (mes=1) em vez de duplicar a linha.
        """
        arrecadacao_raw["keys"]["DtAnoMes"] = "202601"
        campos = _normalizar_agregado(arrecadacao_raw, 2026, 2)
        assert campos["exercicio"] == 2026
        assert campos["mes"] == 1
        assert campos["cod_item_receita"] == "111250010000"
        assert campos["data_emissao"] == date(2026, 2, 11)
        assert campos["valor_arrecadado_periodo"] == Decimal("32813.40")
        assert campos["valor_arrecadado_acumulado"] == Decimal("270631.73")
        assert campos["fonte"] == FONTE_MUNICIPIO_ONLINE

    def test_preserva_dados_brutos(self, arrecadacao_raw):
        campos = _normalizar_agregado(arrecadacao_raw, 2026, 2)
        assert "111250010000" in campos["dados_brutos"]

    def test_campos_opcionais_nulos(self, arrecadacao_raw):
        arrecadacao_raw["descricao_fonte_recurso"] = None
        arrecadacao_raw["cod_fonte_recurso"] = None
        campos = _normalizar_agregado(arrecadacao_raw, 2026, 2)
        assert campos["cod_fonte_recurso"] is None
        assert campos["descricao_fonte_recurso"] is None


class TestNormalizarRecolhimento:
    def test_campos_principais(self):
        raw = {
            "DtEmissao": "05/02/2026",
            "NuProcesso": "2026/00123",
            "DsContaBanco": "BANCO DO BRASIL S.A.",
            "VlRecolhimento": "R$ 15.000,00",
            "DsHistorico": "IPTU cota única",
        }
        campos = _normalizar_recolhimento(raw)
        assert campos["data_emissao"] == date(2026, 2, 5)
        assert campos["numero_processo"] == "2026/00123"
        assert campos["banco"] == "BANCO DO BRASIL S.A."
        assert campos["valor"] == Decimal("15000.00")
        assert campos["historico"] == "IPTU cota única"

    def test_banco_vazio_vira_nao_informado(self):
        raw = {"DsContaBanco": None, "VlRecolhimento": "R$ 10,00"}
        campos = _normalizar_recolhimento(raw)
        assert campos["banco"] == "(não informado)"


# ──────────────────────────────────────────
# Upsert de órgão
# ──────────────────────────────────────────


class TestUpsertsOrgao:
    async def test_cria_novo(self, db_session, arrecadacao_raw, monkeypatch):
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        orgao = await _upsert_orgao_from_municipio_online(db_session, arrecadacao_raw)
        assert orgao.id is not None
        assert orgao.cnpj == TEST_CNPJ_ARRECADACAO
        assert "JEQUIE" in orgao.razao_social.upper()


# ──────────────────────────────────────────
# Pipeline completo (client mockado)
# ──────────────────────────────────────────


class TestPipelineArrecadacao:
    @patch("app.services.ingestao_arrecadacao.MunicipioOnlineClient")
    @patch("app.services.ingestao_arrecadacao.async_session")
    async def test_ingere_agregado_e_detalhe(
        self,
        mock_session_factory,
        mock_client_cls,
        db_session,
        arrecadacao_raw,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        mock_client = AsyncMock()
        mock_client.listar_receitas.return_value = [arrecadacao_raw]
        mock_client.obter_recolhimentos.return_value = [
            {
                "DtEmissao": "05/02/2026",
                "NuProcesso": "2026/00123",
                "DsContaBanco": "BANCO DO BRASIL S.A.",
                "VlRecolhimento": "R$ 15.000,00",
                "DsHistorico": "IPTU cota única",
            },
            {
                "DtEmissao": "12/02/2026",
                "NuProcesso": "2026/00124",
                "DsContaBanco": "CAIXA ECONOMICA FEDERAL",
                "VlRecolhimento": "R$ 17.813,40",
                "DsHistorico": "IPTU parcelado",
            },
        ]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=db_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_arrecadacao(
            exercicio=2026, meses=[2], com_detalhes=True
        )

        assert stats["agregado_criados"] == 1
        assert stats["detalhe_criados"] == 2
        assert stats["erros"] == 0
        assert stats["meses_processados"] == 1

        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_ARRECADACAO)
        )
        test_orgao_id = orgao_res.scalar_one()

        arrecadacoes = await db_session.execute(
            select(Arrecadacao).where(Arrecadacao.orgao_id == test_orgao_id)
        )
        rows = arrecadacoes.scalars().all()
        assert len(rows) == 1
        assert rows[0].valor_arrecadado_periodo == Decimal("32813.40")

        recolhimentos = await db_session.execute(
            select(RecolhimentoDetalhe).where(
                RecolhimentoDetalhe.arrecadacao_id == rows[0].id
            )
        )
        detalhes = recolhimentos.scalars().all()
        assert len(detalhes) == 2
        bancos = {d.banco for d in detalhes}
        assert "BANCO DO BRASIL S.A." in bancos
        assert "CAIXA ECONOMICA FEDERAL" in bancos

    @patch("app.services.ingestao_arrecadacao.MunicipioOnlineClient")
    @patch("app.services.ingestao_arrecadacao.async_session")
    async def test_reingestao_atualiza_sem_duplicar(
        self,
        mock_session_factory,
        mock_client_cls,
        db_session,
        arrecadacao_raw,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        mock_client = AsyncMock()
        mock_client.listar_receitas.return_value = [arrecadacao_raw]
        mock_client.obter_recolhimentos.return_value = []
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=db_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats1 = await ingerir_arrecadacao(exercicio=2026, meses=[2])
        assert stats1["agregado_criados"] == 1

        # Segunda ingestão com valor diferente
        arrecadacao_raw["valor_arrecadado_periodo"] = "R$ 99.999,99"
        mock_client.listar_receitas.return_value = [arrecadacao_raw]

        stats2 = await ingerir_arrecadacao(exercicio=2026, meses=[2])
        assert stats2["agregado_atualizados"] == 1
        assert stats2["agregado_criados"] == 0

        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_ARRECADACAO)
        )
        test_orgao_id = orgao_res.scalar_one()

        rows = (
            await db_session.execute(
                select(Arrecadacao).where(Arrecadacao.orgao_id == test_orgao_id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].valor_arrecadado_periodo == Decimal("99999.99")

    @patch("app.services.ingestao_arrecadacao.MunicipioOnlineClient")
    async def test_fetch_erro_incrementa_erros(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.listar_receitas.side_effect = Exception("timeout")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_arrecadacao(exercicio=2026, meses=[1, 2])
        assert stats["erros"] == 2
        assert stats["meses_processados"] == 0

    @patch("app.services.ingestao_arrecadacao.MunicipioOnlineClient")
    @patch("app.services.ingestao_arrecadacao.async_session")
    async def test_sem_detalhes_nao_chama_drill_down(
        self,
        mock_session_factory,
        mock_client_cls,
        db_session,
        arrecadacao_raw,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        mock_client = AsyncMock()
        mock_client.listar_receitas.return_value = [arrecadacao_raw]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=db_session
        )
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Default agora é com_detalhes=False; não precisa flag.
        stats = await ingerir_arrecadacao(exercicio=2026, meses=[2])
        assert stats["agregado_criados"] == 1
        assert stats["detalhe_criados"] == 0
        # Drill-down nunca foi chamado
        mock_client.obter_recolhimentos.assert_not_called()


# ──────────────────────────────────────────
# Testes de rota (agregação por espécie / banco)
# ──────────────────────────────────────────


class TestRotasArrecadacao:
    async def test_por_especie_agrega_e_calcula_pct(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        # Semear órgão + duas linhas de receita (um imposto + uma taxa).
        orgao = Orgao(cnpj=TEST_CNPJ_ARRECADACAO, razao_social="PREF TESTE", esfera="M")
        db_session.add(orgao)
        await db_session.flush()

        db_session.add(
            Arrecadacao(
                orgao_id=orgao.id,
                cod_ibge="2918001",
                exercicio=2025,
                mes=1,
                cod_item_receita="111250010000",
                descricao_receita="IPTU",
                valor_arrecadado_periodo=Decimal("100000.00"),
                fonte=FONTE_MUNICIPIO_ONLINE,
            )
        )
        db_session.add(
            Arrecadacao(
                orgao_id=orgao.id,
                cod_ibge="2918001",
                exercicio=2025,
                mes=1,
                cod_item_receita="112101010200",
                descricao_receita="TFF",
                valor_arrecadado_periodo=Decimal("25000.00"),
                fonte=FONTE_MUNICIPIO_ONLINE,
            )
        )
        await db_session.flush()

        resp = await client.get("/api/v1/arrecadacao/por-especie?exercicio=2025")
        assert resp.status_code == 200
        dados = resp.json()
        mapa = {d["especie"]: d for d in dados}
        assert mapa["Impostos"]["valor"] == 100000.0
        assert mapa["Taxas"]["valor"] == 25000.0
        assert abs(mapa["Impostos"]["pct"] - 80.0) < 0.01

    async def test_por_banco_agrega_recolhimentos(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        orgao = Orgao(cnpj=TEST_CNPJ_ARRECADACAO, razao_social="PREF TESTE", esfera="M")
        db_session.add(orgao)
        await db_session.flush()

        arr = Arrecadacao(
            orgao_id=orgao.id,
            cod_ibge="2918001",
            exercicio=2025,
            mes=1,
            cod_item_receita="111250010000",
            descricao_receita="IPTU",
            valor_arrecadado_periodo=Decimal("100000.00"),
            fonte=FONTE_MUNICIPIO_ONLINE,
        )
        db_session.add(arr)
        await db_session.flush()

        db_session.add(
            RecolhimentoDetalhe(
                arrecadacao_id=arr.id,
                orgao_id=orgao.id,
                exercicio=2025,
                mes=1,
                banco="BANCO DO BRASIL S.A.",
                valor=Decimal("70000.00"),
            )
        )
        db_session.add(
            RecolhimentoDetalhe(
                arrecadacao_id=arr.id,
                orgao_id=orgao.id,
                exercicio=2025,
                mes=1,
                banco="CAIXA ECONOMICA FEDERAL",
                valor=Decimal("30000.00"),
            )
        )
        await db_session.flush()

        resp = await client.get("/api/v1/arrecadacao/por-banco?exercicio=2025")
        assert resp.status_code == 200
        dados = resp.json()
        assert len(dados) == 2
        assert dados[0]["banco"] == "BANCO DO BRASIL S.A."
        assert dados[0]["valor"] == 70000.0
        assert abs(dados[0]["pct"] - 70.0) < 0.01

    async def test_resumo_nao_infla_previsto_com_varios_meses(
        self, client, db_session, monkeypatch
    ):
        """
        Regressão: `valor_atualizado` carrega a LOA anual e é repetido em cada
        competência ingerida. O resumo deve colapsar por (item, fonte) antes de
        somar, caso contrário o previsto fica multiplicado pelo número de meses.

        Usa exercício 1999 para isolar de dados reais possivelmente presentes
        no banco compartilhado de desenvolvimento.
        """
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        orgao = Orgao(cnpj=TEST_CNPJ_ARRECADACAO, razao_social="PREF TESTE", esfera="M")
        db_session.add(orgao)
        await db_session.flush()

        # IPTU fonte única: LOA anual R$ 1.000.000 repetida em 12 meses,
        # arrecadando R$ 50.000/mês (total R$ 600.000 = 60% realizado).
        for mes in range(1, 13):
            db_session.add(
                Arrecadacao(
                    orgao_id=orgao.id,
                    cod_ibge="2918001",
                    exercicio=1999,
                    mes=mes,
                    cod_item_receita="111250010000",
                    descricao_receita="IPTU",
                    cod_fonte_recurso="15000000",
                    valor_atualizado=Decimal("1000000.00"),
                    valor_arrecadado_periodo=Decimal("50000.00"),
                    fonte=FONTE_MUNICIPIO_ONLINE,
                )
            )
        # Segundo tributo (TFF) com LOA R$ 200.000 em 12 meses, zero arrecadado.
        for mes in range(1, 13):
            db_session.add(
                Arrecadacao(
                    orgao_id=orgao.id,
                    cod_ibge="2918001",
                    exercicio=1999,
                    mes=mes,
                    cod_item_receita="112101010200",
                    descricao_receita="TFF",
                    cod_fonte_recurso=None,
                    valor_atualizado=Decimal("200000.00"),
                    valor_arrecadado_periodo=Decimal("0.00"),
                    fonte=FONTE_MUNICIPIO_ONLINE,
                )
            )
        await db_session.flush()

        resp = await client.get("/api/v1/arrecadacao/resumo?exercicio=1999")
        assert resp.status_code == 200
        dados = resp.json()

        # Previsto anual esperado: IPTU (1.000.000) + TFF (200.000) = 1.200.000.
        # Sem a correção seria 12x mais (14.400.000).
        assert dados["total_previsto"] == 1_200_000.0
        assert dados["total_arrecadado"] == 600_000.0
        assert abs(dados["pct_realizacao"] - 50.0) < 0.01
        assert dados["n_tributos"] == 2

    async def test_historico_por_receita_pivot_top_n(
        self, client, db_session, monkeypatch
    ):
        """
        Pivot plurianual: agrupa por cod_item_receita no intervalo de anos,
        devolve total + valores por ano. Ordena por total desc. Limite
        aplicado ao final.
        """
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        orgao = Orgao(cnpj=TEST_CNPJ_ARRECADACAO, razao_social="PREF TESTE", esfera="M")
        db_session.add(orgao)
        await db_session.flush()

        # Anos históricos fictícios (1990–1992) para isolar do banco real.
        # IPTU arrecada em todos os 3 anos; TFF só em 1991 e 1992.
        dados = [
            (1990, "111250010000", "IPTU Principal", Decimal("100000.00")),
            (1991, "111250010000", "IPTU Principal", Decimal("150000.00")),
            (1992, "111250010000", "IPTU Principal", Decimal("200000.00")),
            (1991, "112101010200", "TFF", Decimal("30000.00")),
            (1992, "112101010200", "TFF", Decimal("40000.00")),
        ]
        for exercicio, cod, desc, valor in dados:
            db_session.add(
                Arrecadacao(
                    orgao_id=orgao.id,
                    cod_ibge="2918001",
                    exercicio=exercicio,
                    mes=1,
                    cod_item_receita=cod,
                    descricao_receita=desc,
                    valor_arrecadado_periodo=valor,
                    fonte=FONTE_MUNICIPIO_ONLINE,
                )
            )
        await db_session.flush()

        resp = await client.get(
            "/api/v1/arrecadacao/historico/por-receita"
            "?ano_inicio=1990&ano_fim=1992&limite=10"
        )
        assert resp.status_code == 200
        body = resp.json()
        mapa = {r["cod_item_receita"]: r for r in body}

        iptu = mapa["111250010000"]
        assert iptu["total"] == 450_000.0
        assert iptu["por_ano"] == {"1990": 100_000.0, "1991": 150_000.0, "1992": 200_000.0}

        tff = mapa["112101010200"]
        assert tff["total"] == 70_000.0
        assert "1990" not in tff["por_ano"]  # ano sem arrecadação omitido
        assert tff["por_ano"] == {"1991": 30_000.0, "1992": 40_000.0}

        # Ordem: IPTU (450k) vem antes de TFF (70k).
        assert body[0]["cod_item_receita"] == "111250010000"

    async def test_historico_por_receita_respeita_intervalo(
        self, client, db_session, monkeypatch
    ):
        """Linhas fora de [ano_inicio, ano_fim] não entram no pivot."""
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        orgao = Orgao(cnpj=TEST_CNPJ_ARRECADACAO, razao_social="PREF TESTE", esfera="M")
        db_session.add(orgao)
        await db_session.flush()

        for ano, valor in [(1990, 100), (1991, 200), (1992, 300)]:
            db_session.add(
                Arrecadacao(
                    orgao_id=orgao.id,
                    cod_ibge="2918001",
                    exercicio=ano,
                    mes=1,
                    cod_item_receita="111250010000",
                    descricao_receita="IPTU",
                    valor_arrecadado_periodo=Decimal(str(valor)),
                    fonte=FONTE_MUNICIPIO_ONLINE,
                )
            )
        await db_session.flush()

        # Só 1991 está no intervalo.
        resp = await client.get(
            "/api/v1/arrecadacao/historico/por-receita"
            "?ano_inicio=1991&ano_fim=1991"
        )
        assert resp.status_code == 200
        # Pode haver registros reais de outros anos, mas esta receita específica
        # só deve aparecer com os 200 de 1991.
        body = resp.json()
        alvo = [r for r in body if r["cod_item_receita"] == "111250010000"]
        assert len(alvo) == 1
        assert alvo[0]["total"] == 200.0

    async def test_historico_mes_x_ano(self, client, db_session, monkeypatch):
        """Agrega (ano, mes) — um ponto por célula."""
        monkeypatch.setattr(
            "app.services.ingestao_arrecadacao.settings.pncp_cnpj_jequie",
            TEST_CNPJ_ARRECADACAO,
        )
        orgao = Orgao(cnpj=TEST_CNPJ_ARRECADACAO, razao_social="PREF TESTE", esfera="M")
        db_session.add(orgao)
        await db_session.flush()

        # 1990/jan: dois tributos somando 500; 1991/fev: um tributo 1000.
        db_session.add(
            Arrecadacao(
                orgao_id=orgao.id,
                cod_ibge="2918001",
                exercicio=1990,
                mes=1,
                cod_item_receita="111250010000",
                descricao_receita="IPTU",
                valor_arrecadado_periodo=Decimal("300.00"),
                fonte=FONTE_MUNICIPIO_ONLINE,
            )
        )
        db_session.add(
            Arrecadacao(
                orgao_id=orgao.id,
                cod_ibge="2918001",
                exercicio=1990,
                mes=1,
                cod_item_receita="112101010200",
                descricao_receita="TFF",
                valor_arrecadado_periodo=Decimal("200.00"),
                fonte=FONTE_MUNICIPIO_ONLINE,
            )
        )
        db_session.add(
            Arrecadacao(
                orgao_id=orgao.id,
                cod_ibge="2918001",
                exercicio=1991,
                mes=2,
                cod_item_receita="111250010000",
                descricao_receita="IPTU",
                valor_arrecadado_periodo=Decimal("1000.00"),
                fonte=FONTE_MUNICIPIO_ONLINE,
            )
        )
        await db_session.flush()

        resp = await client.get(
            "/api/v1/arrecadacao/historico/mes-x-ano?ano_inicio=1990&ano_fim=1991"
        )
        assert resp.status_code == 200
        body = resp.json()
        alvo = [(r["ano"], r["mes"], r["valor"]) for r in body if r["ano"] in (1990, 1991)]
        assert (1990, 1, 500.0) in alvo
        assert (1991, 2, 1000.0) in alvo
