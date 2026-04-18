"""Testes do parser de citações `[n]` no texto gerado pelo LLM."""

from __future__ import annotations

import uuid

from app.services.rag.gerador import parse_citacoes
from app.services.rag.recuperacao import DocumentoRelevante


def _docs(n: int) -> list[DocumentoRelevante]:
    return [
        DocumentoRelevante(
            doc_id=uuid.UUID(int=i),
            fonte="CONTRATO",
            referencia_tipo="contrato",
            referencia_id=None,
            chave_unica=f"contrato:{i}",
            titulo=f"Doc {i}",
            conteudo_texto=f"Corpo {i}",
            metadados={},
            score=0.9 - i * 0.01,
        )
        for i in range(1, n + 1)
    ]


def test_extrai_citacao_simples():
    docs = _docs(3)
    texto = "A despesa com pessoal atingiu 47,28% [2]."
    fontes = parse_citacoes(texto, docs)
    assert len(fontes) == 1
    assert fontes[0].indice == 2
    assert fontes[0].doc_id == docs[1].doc_id


def test_extrai_multiplas_citacoes_unicas():
    docs = _docs(4)
    texto = "Dados [1] combinados com [3] mostram que [1] é relevante."
    fontes = parse_citacoes(texto, docs)
    # [1] aparece duas vezes — só conta uma
    indices = [f.indice for f in fontes]
    assert indices == [1, 3]


def test_descarta_indice_fora_do_range():
    docs = _docs(3)
    texto = "Conforme [5] e também [2]."
    fontes = parse_citacoes(texto, docs)
    # [5] é alucinação; apenas [2] entra
    assert [f.indice for f in fontes] == [2]


def test_descarta_indice_zero_ou_negativo():
    docs = _docs(3)
    # Regex só aceita dígitos; [0] é válido do ponto de vista lexical, mas
    # deve ser descartado por ser fora do range 1-based.
    texto = "Confira [0] e [2]."
    fontes = parse_citacoes(texto, docs)
    assert [f.indice for f in fontes] == [2]


def test_texto_sem_citacoes_retorna_vazio():
    docs = _docs(3)
    texto = "Resposta genérica sem referências."
    fontes = parse_citacoes(texto, docs)
    assert fontes == []


def test_metadados_e_score_sao_propagados():
    docs = _docs(2)
    texto = "Conforme [1]."
    fontes = parse_citacoes(texto, docs)
    assert fontes[0].score == docs[0].score
    assert fontes[0].chave_unica == docs[0].chave_unica
