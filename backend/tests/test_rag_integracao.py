"""
Testes de integração com Vertex AI (Gemini 3.1 Pro + embedding-2).

Todos rodam sob `@pytest.mark.integration` e consomem créditos GCP.
Pulam automaticamente se `gcp_project_id` não estiver configurado.

Cobertura:
- Embeddings têm dimensão correta e task_type assimétrico muda o vetor.
- Ciclo completo: indexa um corpus pequeno in-memory, busca e gera
  resposta com ≥1 citação válida para uma pergunta respondível.
- Golden set: mede recall@6 das chaves esperadas e verifica política de
  citação/recusa em cada uma das 10 perguntas canônicas.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from app.config import get_settings
from app.models.contratacoes import Contrato, Fornecedor
from app.models.orcamento import IndicadorFiscal
from app.services.rag.client import get_gemini_client
from app.services.rag.gerador import responder
from app.services.rag.indexador import reindexar

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente_gemini_real():
    settings = get_settings()
    if not settings.gcp_project_id:
        pytest.skip("gcp_project_id não configurado — pulando integração")
    return get_gemini_client()


# ──────────────────────────────────────────
# Embeddings
# ──────────────────────────────────────────


async def test_embed_dimensao_1536(cliente_gemini_real):
    vetor = await cliente_gemini_real.embed_text(
        "Teste de embedding.", task_type="RETRIEVAL_DOCUMENT"
    )
    assert len(vetor) == 1536
    assert all(isinstance(x, float) for x in vetor)


async def test_task_type_assimetrico_produz_vetores_diferentes(
    cliente_gemini_real,
):
    """O mesmo texto deve produzir embeddings diferentes entre os dois
    task_types — é exatamente para isso que a assimetria serve."""
    texto = "Despesa com pessoal da prefeitura."

    doc = await cliente_gemini_real.embed_text(texto, task_type="RETRIEVAL_DOCUMENT")
    query = await cliente_gemini_real.embed_text(texto, task_type="RETRIEVAL_QUERY")

    assert len(doc) == len(query) == 1536
    # Não devem ser idênticos (task_type muda a representação).
    diferentes = sum(1 for a, b in zip(doc, query, strict=True) if abs(a - b) > 1e-6)
    assert diferentes > 100, (
        "task_type não produziu diferença significativa no embedding — "
        "indica que o output_dimensionality foi aplicado, mas o task_type "
        "possivelmente não."
    )


# ──────────────────────────────────────────
# Ciclo completo com corpus pequeno (in-memory → DB de teste)
# ──────────────────────────────────────────


@pytest.fixture
async def corpus_seed(db_session):
    """Popula o DB de teste com um corpus mínimo e reindexa antes do teste."""
    # Contrato + fornecedor
    fornecedor = Fornecedor(
        cpf_cnpj="88000000000199",
        nome="Tech Solutions Municipal Ltda",
        tipo="PJ",
    )
    db_session.add(fornecedor)
    await db_session.flush()

    contrato = Contrato(
        pncp_id="pncp-test-1",
        numero_contrato="CT-2024-001",
        objeto="Manutenção de sistema de gestão hospitalar do município",
        fornecedor_id=fornecedor.id,
        valor_inicial=Decimal("480000"),
        valor_atual=Decimal("480000"),
        data_inicio_vigencia="2024-01-15",
        data_fim_vigencia="2025-01-14",
        situacao="Vigente",
        categoria="Serviços de TI",
    )
    db_session.add(contrato)

    indicador = IndicadorFiscal(
        exercicio=2024,
        periodo=2,
        codigo="DESPESA_PESSOAL_PCT_RCL",
        descricao="Despesa total com pessoal (% da RCL ajustada)",
        unidade="PERCENTUAL",
        valor=Decimal("47.28"),
        limite_legal=Decimal("54"),
        situacao="OK",
        fonte_relatorio="RGF",
        fonte_exercicio=2024,
        fonte_periodo=2,
        orgao_id=uuid.uuid4(),
    )
    db_session.add(indicador)
    await db_session.commit()

    yield {"contrato_id": contrato.id, "indicador_id": indicador.id}


async def test_ciclo_completo_chat(cliente_gemini_real, corpus_seed, db_session):
    """Indexa corpus mínimo, roda /responder e verifica resposta com citação."""
    # Reindexa todas as fontes relevantes ao corpus seed
    stats = await reindexar(cliente=cliente_gemini_real)
    assert stats["total"] > 0

    resposta = await responder(
        "A prefeitura está dentro do limite de despesa com pessoal?",
        db=db_session,
        cliente=cliente_gemini_real,
        k=6,
    )

    # Deve ter recuperado docs (indicador está no corpus)
    assert resposta.docs_recuperados, "retrieval trouxe zero documentos"
    # Não deve ter recusado (temos o dado)
    assert not resposta.recusou, (
        f"modelo recusou apesar de ter o dado: {resposta.texto!r}"
    )
    # Deve ter citação válida
    assert resposta.fontes, "resposta sem citações — viola regra do prompt"


async def test_recusa_para_pergunta_sem_dado(
    cliente_gemini_real, corpus_seed, db_session
):
    """Pergunta cujo dado não está no corpus deve virar NAO_SEI."""
    resposta = await responder(
        "Quantos funcionários ativos tem a prefeitura hoje?",
        db=db_session,
        cliente=cliente_gemini_real,
        k=6,
    )
    assert resposta.recusou, (
        f"deveria recusar mas respondeu: {resposta.texto!r}"
    )
    assert resposta.fontes == []


# ──────────────────────────────────────────
# Golden set
# ──────────────────────────────────────────


def _match_chave(padrao: str, chave: str) -> bool:
    """Match simples com `*` = wildcard de qualquer sequência."""
    if "*" not in padrao:
        return padrao == chave
    partes = padrao.split("*")
    # todas as partes precisam aparecer em ordem
    idx = 0
    for i, parte in enumerate(partes):
        if not parte:
            continue
        pos = chave.find(parte, idx)
        if pos == -1:
            return False
        if i == 0 and pos != 0:
            return False
        idx = pos + len(parte)
    # última parte precisa casar até o fim se o padrão não termina com *
    if partes[-1] and not chave.endswith(partes[-1]):
        return False
    return True


def _carregar_golden_set() -> list[dict]:
    caminho = Path(__file__).parent / "rag" / "golden_set.yaml"
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("entry", _carregar_golden_set(), ids=lambda e: e["id"])
async def test_golden_set(entry, cliente_gemini_real, db_session):
    """Roda cada pergunta do golden set contra o corpus real já indexado.

    Expectativa: o banco de produção/staging já tem dados ingeridos +
    RAG reindexado. Este teste NÃO popula dados — é um eval contra o
    estado atual do sistema.
    """
    resposta = await responder(
        entry["pergunta"],
        db=db_session,
        cliente=cliente_gemini_real,
        k=6,
    )

    if not entry["deve_citar"]:
        # Recusa esperada
        assert resposta.recusou, (
            f"[{entry['id']}] deveria recusar mas respondeu: {resposta.texto!r}"
        )
        return

    # Perguntas respondíveis: exige recall + citação
    chaves_recuperadas = [d.chave_unica for d in resposta.docs_recuperados]
    esperadas = entry["chaves_esperadas_top6"]
    if esperadas:
        hits = sum(
            1 for padrao in esperadas
            if any(_match_chave(padrao, c) for c in chaves_recuperadas)
        )
        recall = hits / len(esperadas)
        assert recall >= 0.5, (
            f"[{entry['id']}] recall={recall:.2f} < 0.5; "
            f"esperadas={esperadas}; recuperadas={chaves_recuperadas}"
        )

    # Se o modelo respondeu (não recusou), deve ter pelo menos uma citação
    if not resposta.recusou:
        assert resposta.fontes, (
            f"[{entry['id']}] respondeu sem citar: {resposta.texto!r}"
        )
