"""Testes para ingestão RGF + derivação dos indicadores fiscais."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.contratacoes import Orgao
from app.models.orcamento import ExecucaoOrcamentaria, IndicadorFiscal
from app.services.indicadores_fiscais import (
    FATOR_ALERTA,
    INDICADORES,
    SIT_ABAIXO_MINIMO,
    SIT_ALERTA,
    SIT_EXCEDIDO,
    SIT_OK,
    SIT_SEM_DADO,
    _derivar_situacao,
    derivar_indicadores_fiscais,
)
from app.services.ingestao_orcamento import (
    FONTE_RGF,
    TIPO_RELATORIO_RGF,
    _normalizar_rgf,
    ingerir_rgf,
)

TEST_CNPJ_RGF = "99000000999999"


# ──────────────────────────────────────────
# Normalizador RGF
# ──────────────────────────────────────────


class TestNormalizadorRGF:
    def test_normalizar_rgf_marca_tipo_relatorio(self, rgf_item):
        campos = _normalizar_rgf(rgf_item)
        assert campos["tipo_relatorio"] == TIPO_RELATORIO_RGF
        assert campos["fonte"] == FONTE_RGF
        assert campos["periodicidade"] == "Q"
        assert campos["anexo"] == "RGF-Anexo 06"
        assert campos["cod_conta"] == "DespesaTotalComPessoalDemonstrativoSimplificado"
        assert campos["coluna"] == "% SOBRE A RCL AJUSTADA"
        assert campos["valor"] == Decimal("47.28")
        assert campos["cod_ibge"] == "2918001"

    def test_normalizar_rgf_preserva_json_bruto(self, rgf_item):
        campos = _normalizar_rgf(rgf_item)
        assert "DespesaTotalComPessoal" in campos["dados_brutos"]


# ──────────────────────────────────────────
# Derivação de situação
# ──────────────────────────────────────────


class TestDerivarSituacao:
    def test_maximo_ok(self):
        # 47.28 em limite 54 -> 47.28 < 54 * 0.9 (48.6) -> OK
        assert _derivar_situacao(Decimal("47.28"), Decimal("54"), "MAXIMO") == SIT_OK

    def test_maximo_alerta(self):
        # 50 em limite 54 -> 50 >= 48.6 e < 54 -> ALERTA
        assert _derivar_situacao(Decimal("50"), Decimal("54"), "MAXIMO") == SIT_ALERTA

    def test_maximo_excedido(self):
        # 55 em limite 54 -> EXCEDIDO
        assert _derivar_situacao(Decimal("55"), Decimal("54"), "MAXIMO") == SIT_EXCEDIDO

    def test_maximo_limite_exato(self):
        # 54.0 exato -> EXCEDIDO (valor >= limite)
        assert _derivar_situacao(Decimal("54"), Decimal("54"), "MAXIMO") == SIT_EXCEDIDO

    def test_minimo_ok(self):
        # 22.87% em mínimo 15% -> OK
        assert _derivar_situacao(Decimal("22.87"), Decimal("15"), "MINIMO") == SIT_OK

    def test_minimo_abaixo(self):
        # 10% em mínimo 15% -> ABAIXO_MINIMO
        assert (
            _derivar_situacao(Decimal("10"), Decimal("15"), "MINIMO")
            == SIT_ABAIXO_MINIMO
        )

    def test_sem_dado(self):
        assert _derivar_situacao(None, Decimal("54"), "MAXIMO") == SIT_SEM_DADO
        assert _derivar_situacao(None, Decimal("15"), "MINIMO") == SIT_SEM_DADO

    def test_fator_alerta_coerente(self):
        # Garantir que o fator está 0.90 (alinhado com Limite de Alerta do SICONFI).
        assert FATOR_ALERTA == Decimal("0.90")


# ──────────────────────────────────────────
# Catálogo de indicadores
# ──────────────────────────────────────────


class TestCatalogoIndicadores:
    def test_sete_indicadores_registrados(self):
        codigos = {i.codigo for i in INDICADORES}
        esperados = {
            "DESPESA_PESSOAL_PCT_RCL",
            "DESPESA_PESSOAL_PRUDENCIAL",
            "DIVIDA_CONSOLIDADA_PCT_RCL",
            "OP_CREDITO_PCT_RCL",
            "GARANTIAS_PCT_RCL",
            "APLIC_MIN_SAUDE_PCT",
            "APLIC_MIN_EDUCACAO_PCT",
        }
        assert codigos == esperados

    def test_limites_legais(self):
        por_codigo = {i.codigo: i for i in INDICADORES}
        assert por_codigo["DESPESA_PESSOAL_PCT_RCL"].limite_legal == Decimal("54")
        assert por_codigo["DESPESA_PESSOAL_PRUDENCIAL"].limite_legal == Decimal("51.3")
        assert por_codigo["DIVIDA_CONSOLIDADA_PCT_RCL"].limite_legal == Decimal("120")
        assert por_codigo["OP_CREDITO_PCT_RCL"].limite_legal == Decimal("16")
        assert por_codigo["GARANTIAS_PCT_RCL"].limite_legal == Decimal("22")
        assert por_codigo["APLIC_MIN_SAUDE_PCT"].limite_legal == Decimal("15")
        assert por_codigo["APLIC_MIN_EDUCACAO_PCT"].limite_legal == Decimal("25")


# ──────────────────────────────────────────
# Derivador end-to-end
# ──────────────────────────────────────────


async def _seed_orgao_teste(db) -> Orgao:
    orgao = Orgao(cnpj=TEST_CNPJ_RGF, razao_social="ORGAO RGF TESTE", esfera="M", uf="BA")
    db.add(orgao)
    await db.flush()
    return orgao


async def _seed_celula(
    db,
    orgao_id,
    *,
    tipo_relatorio: str,
    anexo: str,
    cod_conta: str,
    coluna: str,
    conta: str,
    valor: Decimal,
    exercicio: int = 2024,
    periodo: int = 2,
) -> ExecucaoOrcamentaria:
    celula = ExecucaoOrcamentaria(
        orgao_id=orgao_id,
        cod_ibge="2918001",
        exercicio=exercicio,
        periodo=periodo,
        periodicidade="Q" if tipo_relatorio == "RGF" else "B",
        tipo_relatorio=tipo_relatorio,
        anexo=anexo,
        rotulo="teste",
        cod_conta=cod_conta,
        coluna=coluna,
        conta=conta,
        valor=valor,
        fonte=f"SICONFI_{tipo_relatorio}",
    )
    db.add(celula)
    await db.flush()
    return celula


class TestDerivarIndicadores:
    @patch("app.services.indicadores_fiscais.async_session")
    async def test_deriva_todos_indicadores_com_fonte_completa(
        self, mock_factory, db_session, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.indicadores_fiscais.get_settings",
            lambda: type("S", (), {"pncp_cnpj_jequie": TEST_CNPJ_RGF})(),
        )
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        orgao = await _seed_orgao_teste(db_session)

        # Todos os 5 indicadores RGF (anexo 06) com valor de teste.
        rgf_combos = {
            "DespesaTotalComPessoalDemonstrativoSimplificado": Decimal("47.28"),
            "DividaConsolidadaLiquidaDemonstrativoSimplificado": Decimal("37.03"),
            "OperacoesDeCreditoInternasEExternasDemonstrativoSimplificado": Decimal("0.02"),
            "GarantiasDemonstrativoSimplificado": Decimal("0.00"),
        }
        for cod_conta, valor in rgf_combos.items():
            await _seed_celula(
                db_session,
                orgao.id,
                tipo_relatorio="RGF",
                anexo="RGF-Anexo 06",
                cod_conta=cod_conta,
                coluna="% SOBRE A RCL AJUSTADA",
                conta=cod_conta,
                valor=valor,
            )

        # Saúde (RREO Anexo 14) — valor 22.87% atende o mínimo de 15%.
        await _seed_celula(
            db_session,
            orgao.id,
            tipo_relatorio="RREO",
            anexo="RREO-Anexo 14",
            cod_conta="AplicacaoTotalDasDespesasComAcoesEServicosPublicosDeSaude",
            coluna="% Aplicado Até o Bimestre",
            conta="Saúde",
            valor=Decimal("22.87"),
            periodo=6,
        )
        # Educação ausente propositalmente → deve virar SEM_DADO.

        stats = await derivar_indicadores_fiscais(exercicio=2024)

        assert stats["total_indicadores"] == 7
        assert stats["criados"] == 7
        assert stats["sem_dado"] == 1  # Educação

        # Verificar situacao caso a caso
        result = await db_session.execute(
            select(IndicadorFiscal).where(IndicadorFiscal.orgao_id == orgao.id)
        )
        por_codigo = {i.codigo: i for i in result.scalars().all()}

        # Despesa pessoal 47.28 em limite 54 -> OK
        assert por_codigo["DESPESA_PESSOAL_PCT_RCL"].valor == Decimal("47.28")
        assert por_codigo["DESPESA_PESSOAL_PCT_RCL"].situacao == SIT_OK
        # Prudencial 47.28 em limite 51.3 -> OK (47.28 < 51.3 * 0.9 = 46.17... na verdade
        # 47.28 > 46.17 portanto ALERTA). 51.3 * 0.9 = 46.17 -> 47.28 >= 46.17 -> ALERTA.
        assert por_codigo["DESPESA_PESSOAL_PRUDENCIAL"].situacao == SIT_ALERTA
        # Dívida 37.03 em limite 120 -> OK
        assert por_codigo["DIVIDA_CONSOLIDADA_PCT_RCL"].situacao == SIT_OK
        # Op crédito 0.02 em limite 16 -> OK
        assert por_codigo["OP_CREDITO_PCT_RCL"].situacao == SIT_OK
        # Garantias 0.00 em limite 22 -> OK
        assert por_codigo["GARANTIAS_PCT_RCL"].situacao == SIT_OK
        # Saúde 22.87 >= 15 -> OK
        assert por_codigo["APLIC_MIN_SAUDE_PCT"].valor == Decimal("22.87")
        assert por_codigo["APLIC_MIN_SAUDE_PCT"].situacao == SIT_OK
        # Educação sem dado
        assert por_codigo["APLIC_MIN_EDUCACAO_PCT"].valor is None
        assert por_codigo["APLIC_MIN_EDUCACAO_PCT"].situacao == SIT_SEM_DADO

    @patch("app.services.indicadores_fiscais.async_session")
    async def test_reingestao_atualiza_indicadores(
        self, mock_factory, db_session, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.indicadores_fiscais.get_settings",
            lambda: type("S", (), {"pncp_cnpj_jequie": TEST_CNPJ_RGF})(),
        )
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        orgao = await _seed_orgao_teste(db_session)
        celula = await _seed_celula(
            db_session,
            orgao.id,
            tipo_relatorio="RGF",
            anexo="RGF-Anexo 06",
            cod_conta="DespesaTotalComPessoalDemonstrativoSimplificado",
            coluna="% SOBRE A RCL AJUSTADA",
            conta="teste",
            valor=Decimal("40"),
        )

        stats1 = await derivar_indicadores_fiscais(exercicio=2024)
        assert stats1["criados"] == 7

        # Atualizar valor e rederivar
        celula.valor = Decimal("55")  # excedido
        await db_session.flush()

        stats2 = await derivar_indicadores_fiscais(exercicio=2024)
        assert stats2["atualizados"] == 7
        assert stats2["criados"] == 0

        result = await db_session.execute(
            select(IndicadorFiscal).where(
                IndicadorFiscal.orgao_id == orgao.id,
                IndicadorFiscal.codigo == "DESPESA_PESSOAL_PCT_RCL",
            )
        )
        ind = result.scalar_one()
        assert ind.valor == Decimal("55")
        assert ind.situacao == SIT_EXCEDIDO


# ──────────────────────────────────────────
# Pipeline RGF (com mocks)
# ──────────────────────────────────────────


class TestPipelineRGF:
    @patch("app.services.ingestao_orcamento.SICONFIClient")
    @patch("app.services.ingestao_orcamento.async_session")
    async def test_ingerir_rgf_cria_celula(
        self, mock_factory, mock_client_cls, db_session, rgf_item, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.ingestao_orcamento.settings.pncp_cnpj_jequie",
            TEST_CNPJ_RGF,
        )
        mock_siconfi = AsyncMock()
        mock_siconfi.paginar_rgf.return_value = [rgf_item]
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_siconfi)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_rgf(exercicio=2024, quadrimestres=[2])

        assert stats["criados"] == 1
        assert stats["erros"] == 0
        assert stats["periodos_processados"] == 1
        assert stats["periodos_vazios"] == 0

        orgao_res = await db_session.execute(
            select(Orgao.id).where(Orgao.cnpj == TEST_CNPJ_RGF)
        )
        orgao_id = orgao_res.scalar_one()

        result = await db_session.execute(
            select(ExecucaoOrcamentaria).where(
                ExecucaoOrcamentaria.orgao_id == orgao_id,
                ExecucaoOrcamentaria.tipo_relatorio == TIPO_RELATORIO_RGF,
                ExecucaoOrcamentaria.exercicio == 2024,
                ExecucaoOrcamentaria.periodo == 2,
            )
        )
        registros = result.scalars().all()
        assert len(registros) == 1
        assert registros[0].fonte == FONTE_RGF
        assert registros[0].periodicidade == "Q"

    @patch("app.services.ingestao_orcamento.SICONFIClient")
    async def test_ingerir_rgf_quadrimestre_vazio_nao_eh_erro(self, mock_client_cls):
        mock_siconfi = AsyncMock()
        # Q3 típico: ainda não homologado → API devolve []
        mock_siconfi.paginar_rgf.return_value = []
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_siconfi)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        stats = await ingerir_rgf(exercicio=2024, quadrimestres=[3])

        assert stats["erros"] == 0
        assert stats["criados"] == 0
        assert stats["periodos_processados"] == 0
        assert stats["periodos_vazios"] == 1
