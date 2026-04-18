"""
Validação de request do endpoint `/chat`.

Esses testes batem apenas o contrato de entrada do endpoint (Pydantic).
Não fazem chamada ao Gemini — sobrepõem `_cliente_gemini` por um stub
via `app.dependency_overrides` para evitar que a resolução de dependências
tente instanciar o cliente real (que exigiria GCP configurado).

Rate limit (429) e fluxo feliz completo são cobertos nos testes de
integração (`test_rag_integracao.py`).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes.chat import _cliente_gemini
from app.main import app


class _ClienteStub:
    """Cliente dummy — não faz nada; usado só para satisfazer DI."""

    pass


@pytest.fixture(autouse=True)
def _sobrescrever_cliente_gemini():
    """Evita instanciar o GeminiClient real (que exige GCP configurado).

    Aplicado a todos os testes neste módulo via `autouse=True`.
    """
    app.dependency_overrides[_cliente_gemini] = lambda: _ClienteStub()
    try:
        yield
    finally:
        app.dependency_overrides.pop(_cliente_gemini, None)


async def test_pergunta_curta_retorna_422():
    """Pergunta com menos de 3 caracteres é rejeitada pelo schema."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        resp = await c.post("/api/v1/chat/", json={"pergunta": "oi"})
    assert resp.status_code == 422


async def test_pergunta_muito_longa_retorna_422():
    """Pergunta com mais de 500 caracteres é rejeitada."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        resp = await c.post("/api/v1/chat/", json={"pergunta": "x" * 501})
    assert resp.status_code == 422


async def test_payload_invalido_retorna_422():
    """Corpo sem `pergunta` é rejeitado."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        resp = await c.post("/api/v1/chat/", json={})
    assert resp.status_code == 422
