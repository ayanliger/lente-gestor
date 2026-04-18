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
    LinhaResumoPCA,
    renderizar_contrato,
    renderizar_indicador_fiscal,
    renderizar_resumo_funcao,
    renderizar_resumo_pca,
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
