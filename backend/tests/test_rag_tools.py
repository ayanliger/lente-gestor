"""Testes das tools (function calling) — execução SQL + renumeração de citações."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.contratacoes import Contrato, Fornecedor
from app.models.rag import DocumentoRag, FonteDocumento
from app.services.rag.gerador import _wrapear_tools
from app.services.rag.recuperacao import DocumentoRelevante
from app.services.rag.tools import (
    construir_registry_padrao,
    executar_buscar_contratos,
    executar_contratos_vencendo,
)


class _FakeGeminiClient:
    """Cliente que devolve embeddings determinísticos por palavra-chave.

    O vetor da "query" é igualado ao vetor inserido em ``documentos_rag``
    do contrato que casa com a categoria, garantindo distância cosseno = 0
    e similaridade = 1.0. Demais contratos têm embeddings ortogonais.
    """

    def __init__(self, mapa_termo_vetor: dict[str, list[float]]):
        self._mapa = mapa_termo_vetor

    async def embed_text(self, texto: str, *, task_type: str) -> list[float]:
        chave = texto.strip().lower()
        if chave in self._mapa:
            return self._mapa[chave]
        # Fallback: vetor zero (similaridade 0.0)
        return [0.0] * 1536

# ──────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────


@pytest.fixture
async def corpus_contratos(db_session):
    """Insere um pequeno corpus de contratos com vigências determinísticas.

    Garante:
    - 2 contratos terminando em ≤30 dias (um de TI, um de limpeza)
    - 1 contrato terminando em ~120 dias
    - 1 contrato vencido (data passada)
    - 1 contrato sem data_fim_vigencia

    Os contratos não referenciam um órgão (FK é nulável) para evitar
    colisão com o órgão real já ingerido em ambiente de teste local.
    Fornecedores usam CNPJs `99...`, convenção de teste do conftest.

    Limpa `contratos` no início do teste para que os assertions
    não se misturem com a base real ingerida — a transação externa do
    conftest faz rollback ao fim, restaurando os dados originais.
    """
    await db_session.execute(text("DELETE FROM contratos"))
    fornecedor_ti = Fornecedor(
        cpf_cnpj="99000000000311",
        nome="Tech Jequié Soluções Ltda (TESTE)",
        tipo="PJ",
    )
    fornecedor_limpeza = Fornecedor(
        cpf_cnpj="99000000000322",
        nome="Limpa Bem Servicos S.A. (TESTE)",
        tipo="PJ",
    )
    db_session.add_all([fornecedor_ti, fornecedor_limpeza])
    await db_session.flush()

    hoje = date.today()
    contratos = [
        Contrato(
            pncp_id="pncp-ti-30",
            numero_contrato="CT-2025-001",
            ano=2025,
            objeto="Manutenção do sistema de tecnologia da informação municipal",
            categoria="TI",
            valor_inicial=Decimal("180000.00"),
            valor_atual=Decimal("180000.00"),
            data_inicio_vigencia=hoje - timedelta(days=335),
            data_fim_vigencia=hoje + timedelta(days=30),
            situacao="Vigente",
            fornecedor_id=fornecedor_ti.id,
        ),
        Contrato(
            pncp_id="pncp-limpeza-15",
            numero_contrato="CT-2025-002",
            ano=2025,
            objeto="Serviços de limpeza e conservação de prédios públicos",
            categoria="Serviços gerais",
            valor_inicial=Decimal("450000.00"),
            valor_atual=Decimal("450000.00"),
            data_inicio_vigencia=hoje - timedelta(days=350),
            data_fim_vigencia=hoje + timedelta(days=15),
            situacao="Vigente",
            fornecedor_id=fornecedor_limpeza.id,
        ),
        Contrato(
            pncp_id="pncp-ti-120",
            numero_contrato="CT-2025-003",
            ano=2025,
            objeto="Hospedagem e suporte de tecnologia em nuvem",
            categoria="TI",
            valor_inicial=Decimal("90000.00"),
            valor_atual=Decimal("90000.00"),
            data_inicio_vigencia=hoje - timedelta(days=245),
            data_fim_vigencia=hoje + timedelta(days=120),
            situacao="Vigente",
            fornecedor_id=fornecedor_ti.id,
        ),
        Contrato(
            pncp_id="pncp-vencido",
            numero_contrato="CT-2024-999",
            ano=2024,
            objeto="Contrato antigo de tecnologia já vencido",
            categoria="TI",
            valor_inicial=Decimal("30000.00"),
            data_inicio_vigencia=hoje - timedelta(days=730),
            data_fim_vigencia=hoje - timedelta(days=10),
            situacao="Encerrado",
            fornecedor_id=fornecedor_ti.id,
        ),
        Contrato(
            pncp_id="pncp-sem-data",
            numero_contrato="CT-2025-004",
            ano=2025,
            objeto="Locação de imóvel residencial",
            categoria="Locação",
            valor_inicial=Decimal("12000.00"),
            data_inicio_vigencia=hoje - timedelta(days=60),
            data_fim_vigencia=None,
            situacao="Vigente",
        ),
    ]
    db_session.add_all(contratos)
    await db_session.commit()
    return contratos


# ──────────────────────────────────────────
# contratos_vencendo
# ──────────────────────────────────────────


async def test_contratos_vencendo_padrao_lista_dentro_da_janela(
    db_session, corpus_contratos
):
    resultado = await executar_contratos_vencendo(db=db_session, dias=90)

    chaves = {d.chave_unica for d in resultado.docs}
    # Os 2 contratos com fim em 15/30 dias devem aparecer; o de 120 dias NÃO.
    assert any(c.numero_contrato == "CT-2025-001" for c in corpus_contratos)
    assert len(resultado.docs) == 2
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    assert numeros == {"CT-2025-001", "CT-2025-002"}
    # Não deve incluir contrato vencido nem o sem data_fim
    assert "contrato:" + str(corpus_contratos[3].id) not in chaves  # vencido
    assert "contrato:" + str(corpus_contratos[4].id) not in chaves  # sem data
    # Texto contém numeração [1]…[2] e indicação da janela
    assert "[1]" in resultado.texto
    assert "[2]" in resultado.texto
    assert "janela de 90 dias" in resultado.texto


async def test_contratos_vencendo_filtra_por_categoria(db_session, corpus_contratos):
    resultado = await executar_contratos_vencendo(
        db=db_session, dias=90, categoria_objeto="tecnologia"
    )
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    # Só o de TI dentro da janela (limpeza fica fora porque o objeto não tem
    # nem o termo 'tecnologia' nem categoria 'TI' bate ILIKE %tecnologia%).
    assert numeros == {"CT-2025-001"}


async def test_contratos_vencendo_clampa_dias_acima_do_maximo(
    db_session, corpus_contratos
):
    # 9999 dias deve ser limitado a 365; ainda assim só os 3 com data
    # futura entram no resultado.
    resultado = await executar_contratos_vencendo(db=db_session, dias=9999)
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    assert numeros == {"CT-2025-001", "CT-2025-002", "CT-2025-003"}


async def test_contratos_vencendo_sem_resultados(db_session, corpus_contratos):
    resultado = await executar_contratos_vencendo(
        db=db_session, dias=5, categoria_objeto="aeronave"
    )
    assert resultado.docs == []
    assert "Nenhum contrato" in resultado.texto


# ──────────────────────────────────────────
# buscar_contratos
# ──────────────────────────────────────────


async def test_buscar_contratos_por_substring_objeto(db_session, corpus_contratos):
    resultado = await executar_buscar_contratos(db=db_session, busca="tecnologia")
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    assert numeros == {"CT-2025-001", "CT-2025-003", "CT-2024-999"}


async def test_buscar_contratos_por_fornecedor(db_session, corpus_contratos):
    resultado = await executar_buscar_contratos(
        db=db_session, fornecedor_nome="Limpa Bem"
    )
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    assert numeros == {"CT-2025-002"}


async def test_buscar_contratos_por_ano(db_session, corpus_contratos):
    resultado = await executar_buscar_contratos(db=db_session, ano=2024)
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    assert numeros == {"CT-2024-999"}


async def test_buscar_contratos_recusa_sem_filtros(db_session, corpus_contratos):
    """Sem nenhum filtro, a tool recusa em vez de listar tudo."""
    resultado = await executar_buscar_contratos(db=db_session)
    assert resultado.docs == []
    assert "exige pelo menos um filtro" in resultado.texto


# ──────────────────────────────────────────
# Wrapper: renumeração de citações
# ──────────────────────────────────────────


def _doc_rag(i: int) -> DocumentoRelevante:
    return DocumentoRelevante(
        doc_id=uuid.UUID(int=i),
        fonte="CONTRATO",
        referencia_tipo="contrato",
        referencia_id=None,
        chave_unica=f"rag:{i}",
        titulo=f"Doc RAG {i}",
        conteudo_texto=f"Corpo {i}",
        metadados={},
        score=0.9,
    )


async def test_wrapper_renumera_indices_para_offset_global(
    db_session, corpus_contratos
):
    """O wrapper deve deslocar `[1]→[N+1]` no texto e somar docs ao pool.

    Cobre o contrato pelo qual cita\u00e7\u00f5es do modelo apontam direto para o
    \u00edndice correto em `docs_acumulados` mesmo quando j\u00e1 h\u00e1 docs RAG
    pr\u00e9-existentes no in\u00edcio.
    """
    docs_acumulados: list[DocumentoRelevante] = [_doc_rag(1), _doc_rag(2)]
    registry = construir_registry_padrao()
    executores = _wrapear_tools(
        registry=registry, db=db_session, docs_acumulados=docs_acumulados
    )
    response = await executores["contratos_vencendo"](dias=90)

    # 2 docs vencendo no corpus (15 e 30 dias)
    assert response["qtd_resultados"] == 2
    assert response["indice_inicial"] == 3
    assert response["indice_final"] == 4
    # O texto retornado deve ter [3] e [4], NÃO [1] e [2]
    assert "[3]" in response["texto"]
    assert "[4]" in response["texto"]
    assert "[1]" not in response["texto"]
    assert "[2]" not in response["texto"]
    # Pool acumulado virou RAG(2) + tool(2)
    assert len(docs_acumulados) == 4
    assert docs_acumulados[2].fonte == "CONTRATO"
    assert docs_acumulados[2].metadados.get("fonte_tool") == "contratos_vencendo"


async def test_wrapper_propaga_erro_da_tool_sem_quebrar_loop(
    db_session, corpus_contratos
):
    """Tool inv\u00e1lida (sem filtros) ainda retorna dict serializ\u00e1vel."""
    docs_acumulados: list[DocumentoRelevante] = []
    registry = construir_registry_padrao()
    executores = _wrapear_tools(
        registry=registry, db=db_session, docs_acumulados=docs_acumulados
    )
    response = await executores["buscar_contratos"]()

    assert response["qtd_resultados"] == 0
    assert "exige pelo menos um filtro" in response["texto"]
    assert docs_acumulados == []


# ──────────────────────────────────────────
# Registry
# ──────────────────────────────────────────


def test_registry_padrao_expoe_tools_esperadas():
    registry = construir_registry_padrao()
    assert sorted(registry.nomes) == ["buscar_contratos", "contratos_vencendo"]
    assert set(registry.executors) == {"buscar_contratos", "contratos_vencendo"}


# ───────────────────────────────────────────
# Ranking semântico (cliente fake)
# ───────────────────────────────────────────


@pytest.fixture
async def corpus_com_embeddings(db_session, corpus_contratos):
    """Insere DocumentoRag com vetores fixos para 2 contratos da janela.

    Vetor `vetor_tech` aponta para Contrato CT-2025-001 (TI). Vetor
    `vetor_distante` (ortogonal) cobre Contrato CT-2025-002 (limpeza).
    Permite verificar que o ranking semântico só retorna o que estiver
    próximo do termo embedado.
    """
    vetor_tech = [0.0] * 1536
    vetor_tech[0] = 1.0  # vector na primeira coordenada
    vetor_distante = [0.0] * 1536
    vetor_distante[7] = 1.0  # ortogonal ao vetor_tech

    contrato_ti = next(c for c in corpus_contratos if c.numero_contrato == "CT-2025-001")
    contrato_limpeza = next(
        c for c in corpus_contratos if c.numero_contrato == "CT-2025-002"
    )

    docs = [
        DocumentoRag(
            fonte=FonteDocumento.CONTRATO.value,
            referencia_tipo="contrato",
            referencia_id=contrato_ti.id,
            chave_unica=f"contrato:{contrato_ti.id}",
            titulo="Contrato TI",
            conteudo_texto="Sistema de tecnologia da informação",
            metadados={},
            embedding=vetor_tech,
            modelo_embedding="fake@1536",
            hash_conteudo=hashlib.sha256(b"ti").hexdigest(),
        ),
        DocumentoRag(
            fonte=FonteDocumento.CONTRATO.value,
            referencia_tipo="contrato",
            referencia_id=contrato_limpeza.id,
            chave_unica=f"contrato:{contrato_limpeza.id}",
            titulo="Contrato Limpeza",
            conteudo_texto="Serviços de limpeza e conservação",
            metadados={},
            embedding=vetor_distante,
            modelo_embedding="fake@1536",
            hash_conteudo=hashlib.sha256(b"limpeza").hexdigest(),
        ),
    ]
    db_session.add_all(docs)
    await db_session.commit()
    return {"vetor_tech": vetor_tech, "vetor_distante": vetor_distante}


async def test_contratos_vencendo_usa_ranking_semantico_quando_cliente_disponivel(
    db_session, corpus_com_embeddings
):
    """Termo 'tecnologia' embedado deve casar só com o contrato de TI.

    Crucialmente, o objeto do contrato de TI (CT-2025-001) contém a palavra
    'tecnologia' literalmente, mas o teste é sobre o caminho **semântico**:
    o vetor da query é igual ao vetor do doc → distance=0 → similarity=1.0
    → passa o limiar. O contrato de limpeza tem vetor ortogonal →
    similarity=0 → fica abaixo do limiar e é descartado.
    """
    cliente = _FakeGeminiClient(
        {"tecnologia": corpus_com_embeddings["vetor_tech"]}
    )
    resultado = await executar_contratos_vencendo(
        db=db_session, cliente=cliente, dias=90, categoria_objeto="tecnologia"
    )
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    assert numeros == {"CT-2025-001"}
    # Cabeçalho indica modo semântico
    assert "semanticamente" in resultado.texto
    # Score é ~1.0 já que vetor da query == vetor do doc
    assert resultado.docs[0].score >= 0.99
    assert resultado.docs[0].metadados["similaridade"] >= 0.99


async def test_contratos_vencendo_semantico_descarta_abaixo_do_limiar(
    db_session, corpus_com_embeddings
):
    """Termo cuja embedding não casa com nenhum doc retorna lista vazia."""
    cliente = _FakeGeminiClient({})  # ZERO vector for any term
    resultado = await executar_contratos_vencendo(
        db=db_session, cliente=cliente, dias=90, categoria_objeto="aeroespacial"
    )
    assert resultado.docs == []
    assert "Nenhum contrato" in resultado.texto


async def test_contratos_vencendo_fallback_estrutural_sem_cliente(
    db_session, corpus_contratos
):
    """Sem cliente, mantém o filtro estrutural (ILIKE) original."""
    resultado = await executar_contratos_vencendo(
        db=db_session, dias=90, categoria_objeto="tecnologia"
    )
    numeros = {d.metadados["numero_contrato"] for d in resultado.docs}
    # ILIKE encontra apenas o contrato cujo objeto contém a palavra exata.
    assert numeros == {"CT-2025-001"}
    assert "literalmente" in resultado.texto
