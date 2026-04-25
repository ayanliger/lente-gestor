"""Testes unitários dos renderizadores RAG — sem rede, sem banco."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.contratacoes import Contrato, Fornecedor
from app.models.orcamento import IndicadorFiscal
from app.models.rag import FonteDocumento
from app.services.rag.renderizadores import (
    LinhaResumoFuncao,
    LinhaResumoNaturezaDespesa,
    LinhaResumoPCA,
    LinhaResumoReceita,
    renderizar_contrato,
    renderizar_indicador_fiscal,
    renderizar_resumo_funcao,
    renderizar_resumo_natureza_despesa,
    renderizar_resumo_pca,
    renderizar_resumo_receita,
)


def _contrato_fixture() -> Contrato:
    c = Contrato()
    c.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    c.pncp_id = "pncp-123"
    c.numero_contrato = "CT-001/2025"
    c.objeto = "Aquisição de medicamentos para a rede básica de saúde"
    c.valor_inicial = Decimal("150000.00")
    c.valor_atual = Decimal("165000.00")
    c.valor_aditivos = Decimal("15000.00")
    c.data_assinatura = date(2025, 3, 1)
    c.data_inicio_vigencia = date(2025, 3, 10)
    c.data_fim_vigencia = date(2026, 3, 9)
    c.situacao = "Vigente"
    c.categoria = "Compras"
    c.subcategoria = "Medicamentos"
    return c


def _fornecedor_fixture() -> Fornecedor:
    f = Fornecedor()
    f.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    f.cpf_cnpj = "12345678000199"
    f.nome = "Distribuidora Farmacêutica ABC Ltda"
    f.tipo = "PJ"
    return f


def test_renderizar_contrato_produz_chave_e_metadados():
    contrato = _contrato_fixture()
    fornecedor = _fornecedor_fixture()

    doc = renderizar_contrato(contrato, fornecedor)

    assert doc.fonte == FonteDocumento.CONTRATO
    assert doc.chave_unica == f"contrato:{contrato.id}"
    assert doc.referencia_id == contrato.id
    assert doc.referencia_tipo == "contrato"
    # Metadados estruturados
    assert doc.metadados["numero_contrato"] == "CT-001/2025"
    assert doc.metadados["fornecedor_cnpj"] == "12345678000199"
    assert doc.metadados["valor_inicial"] == 150000.00
    # Texto contém informação mínima
    assert "CT-001/2025" in doc.conteudo_texto
    assert "medicamentos" in doc.conteudo_texto.lower()
    assert "Distribuidora" in doc.conteudo_texto


def test_renderizar_contrato_sem_fornecedor_nao_quebra():
    contrato = _contrato_fixture()
    doc = renderizar_contrato(contrato, None)
    assert "fornecedor não identificado" in doc.conteudo_texto


def test_renderizar_contrato_trunca_titulo_longo():
    contrato = _contrato_fixture()
    contrato.objeto = "x" * 600  # bem acima de 500
    doc = renderizar_contrato(contrato, None)
    assert len(doc.titulo) <= 500


def test_hash_conteudo_muda_quando_texto_muda():
    contrato = _contrato_fixture()
    doc_a = renderizar_contrato(contrato, None)

    contrato.valor_inicial = Decimal("200000.00")
    doc_b = renderizar_contrato(contrato, None)

    assert doc_a.hash_conteudo != doc_b.hash_conteudo
    assert doc_a.chave_unica == doc_b.chave_unica


def test_renderizar_indicador_fiscal_narrativa_legivel():
    ind = IndicadorFiscal()
    ind.id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    ind.exercicio = 2024
    ind.periodo = 2
    ind.codigo = "DESPESA_PESSOAL_PCT_RCL"
    ind.descricao = "Despesa total com pessoal (% da RCL ajustada)"
    ind.unidade = "PERCENTUAL"
    ind.valor = Decimal("47.28")
    ind.limite_legal = Decimal("54")
    ind.situacao = "OK"
    ind.fonte_relatorio = "RGF"
    ind.fonte_exercicio = 2024
    ind.fonte_periodo = 2

    doc = renderizar_indicador_fiscal(ind)

    assert doc.fonte == FonteDocumento.INDICADOR_FISCAL
    assert doc.chave_unica == f"indicador:{ind.id}"
    assert "47.28%" in doc.conteudo_texto
    assert "54.00%" in doc.conteudo_texto
    assert "OK" in doc.conteudo_texto
    assert doc.metadados["situacao"] == "OK"


def test_renderizar_resumo_funcao_calcula_pct_execucao():
    linha = LinhaResumoFuncao(
        exercicio=2024,
        periodo=6,
        funcao="Saúde",
        dotacao_inicial=Decimal("120000000"),
        dotacao_atualizada=Decimal("125000000"),
        empenhado=Decimal("100000000"),
        liquidado=Decimal("95000000"),
        saldo=Decimal("25000000"),
    )

    doc = renderizar_resumo_funcao(linha)

    assert doc.fonte == FonteDocumento.RESUMO_FUNCAO
    assert doc.chave_unica == "resumo_funcao:2024:6:Saúde"
    assert doc.referencia_id is None  # agregado
    # 100M / 125M = 80.0%
    assert doc.metadados["pct_execucao"] == 80.0
    assert "80.0%" in doc.conteudo_texto


def test_renderizar_resumo_pca_calcula_desvio():
    linha = LinhaResumoPCA(
        exercicio=2024,
        funcao="Educação",
        qtd_itens=42,
        valor_estimado_total=Decimal("50000000"),
        valor_executado_total=Decimal("60000000"),  # passou do planejado
        situacao_predominante="Em execução",
    )

    doc = renderizar_resumo_pca(linha)

    assert doc.fonte == FonteDocumento.RESUMO_PCA
    assert doc.chave_unica == "resumo_pca:2024:Educação"
    assert doc.metadados["pct_execucao"] == 120.0
    assert "120.0%" in doc.conteudo_texto
    assert "Em execução" in doc.conteudo_texto


def test_renderizar_resumo_receita_calcula_pct_arrecadacao():
    linha = LinhaResumoReceita(
        exercicio=2024,
        periodo=6,
        categoria_codigo="ReceitaTributaria",
        categoria_legivel="Tributária",
        previsao_inicial=Decimal("50000000"),
        previsao_atualizada=Decimal("60000000"),
        arrecadado_no_bimestre=Decimal("10000000"),
        arrecadado_ate_bimestre=Decimal("45000000"),  # 45M / 60M = 75%
        saldo=Decimal("15000000"),
    )

    doc = renderizar_resumo_receita(linha)

    assert doc.fonte == FonteDocumento.RESUMO_RECEITA
    assert doc.chave_unica == "resumo_receita:2024:6:ReceitaTributaria"
    assert doc.referencia_id is None  # agregado
    assert doc.metadados["pct_arrecadacao"] == 75.0
    assert doc.metadados["categoria_legivel"] == "Tributária"
    assert "75.0%" in doc.conteudo_texto
    assert "Tributária" in doc.conteudo_texto
    assert "bimestre 6" in doc.conteudo_texto


def test_renderizar_resumo_receita_sem_previsao_omite_pct():
    """Previsão zero ou nula não pode gerar divisão por zero."""
    linha = LinhaResumoReceita(
        exercicio=2024,
        periodo=1,
        categoria_codigo="AlienacaoDeBens",
        categoria_legivel="Alienação de Bens",
        previsao_inicial=None,
        previsao_atualizada=None,
        arrecadado_no_bimestre=None,
        arrecadado_ate_bimestre=Decimal("100"),
        saldo=None,
    )

    doc = renderizar_resumo_receita(linha)

    assert doc.metadados["pct_arrecadacao"] is None
    assert "Percentual de realização" not in doc.conteudo_texto


def test_renderizar_resumo_natureza_despesa_calcula_pct_execucao():
    linha = LinhaResumoNaturezaDespesa(
        exercicio=2024,
        periodo=6,
        natureza_codigo="PessoalEEncargosSociais",
        natureza_legivel="Pessoal e Encargos Sociais",
        dotacao_inicial=Decimal("400000000"),
        dotacao_atualizada=Decimal("500000000"),
        empenhado=Decimal("450000000"),  # 450M / 500M = 90%
        liquidado=Decimal("440000000"),
        saldo=Decimal("50000000"),
    )

    doc = renderizar_resumo_natureza_despesa(linha)

    assert doc.fonte == FonteDocumento.RESUMO_NATUREZA_DESPESA
    assert (
        doc.chave_unica
        == "resumo_natureza:2024:6:PessoalEEncargosSociais"
    )
    assert doc.referencia_id is None
    assert doc.metadados["pct_execucao"] == 90.0
    assert doc.metadados["natureza_legivel"] == "Pessoal e Encargos Sociais"
    assert "90.0%" in doc.conteudo_texto
    assert "Pessoal e Encargos Sociais" in doc.conteudo_texto


def test_renderizar_resumo_natureza_despesa_capex_em_titulo():
    linha = LinhaResumoNaturezaDespesa(
        exercicio=2025,
        periodo=3,
        natureza_codigo="Investimentos",
        natureza_legivel="Investimentos (CAPEX)",
        dotacao_inicial=Decimal("30000000"),
        dotacao_atualizada=Decimal("40000000"),
        empenhado=Decimal("5000000"),
        liquidado=Decimal("4000000"),
        saldo=Decimal("35000000"),
    )

    doc = renderizar_resumo_natureza_despesa(linha)

    assert "CAPEX" in doc.titulo
    assert "2025/B3" in doc.titulo
