"""Testes unitários dos templates de prompt."""

from __future__ import annotations

import uuid

from app.services.rag.prompts import (
    MARCADOR_RECUSA,
    SYSTEM_PROMPT,
    montar_prompt_usuario,
)
from app.services.rag.recuperacao import DocumentoRelevante


def _doc(titulo: str, conteudo: str, score: float = 0.9) -> DocumentoRelevante:
    return DocumentoRelevante(
        doc_id=uuid.uuid4(),
        fonte="CONTRATO",
        referencia_tipo="contrato",
        referencia_id=uuid.uuid4(),
        chave_unica=f"contrato:{uuid.uuid4()}",
        titulo=titulo,
        conteudo_texto=conteudo,
        metadados={},
        score=score,
    )


def test_system_prompt_contem_regras_criticas():
    assert MARCADOR_RECUSA in SYSTEM_PROMPT
    assert "[n]" in SYSTEM_PROMPT
    assert "CRUZAMENTO" in SYSTEM_PROMPT.upper()
    assert "Jequié" in SYSTEM_PROMPT


def test_prompt_usuario_numera_documentos():
    docs = [
        _doc("Contrato A", "Objeto A"),
        _doc("Contrato B", "Objeto B"),
        _doc("Contrato C", "Objeto C"),
    ]
    prompt = montar_prompt_usuario("Qual o valor?", docs)

    assert "PERGUNTA DO GESTOR" in prompt
    assert "DOCUMENTOS RECUPERADOS PARA ESTA PERGUNTA" in prompt
    assert "Qual o valor?" in prompt
    assert "[1] Contrato A" in prompt
    assert "[2] Contrato B" in prompt
    assert "[3] Contrato C" in prompt
    # Corpo dos documentos presente
    assert "Objeto A" in prompt
    assert "Objeto C" in prompt


def test_prompt_usuario_sem_documentos():
    prompt = montar_prompt_usuario("Pergunta sem contexto", [])
    assert "nenhum documento relevante" in prompt
    assert MARCADOR_RECUSA in prompt  # lembrete de recusa no rodapé


def test_prompt_usuario_inclui_historico_quando_fornecido():
    prompt = montar_prompt_usuario(
        "Essa observação é verdadeira?",
        [_doc("Cobertura", "Há dados por função de 2020 a 2026.")],
        historico="usuario: Quais dados faltam?\nassistente: Faltam dados.",
    )

    assert "CONTEXTO RECENTE DA CONVERSA" in prompt
    assert "usuario: Quais dados faltam?" in prompt
    assert "Essa observação é verdadeira?" in prompt
