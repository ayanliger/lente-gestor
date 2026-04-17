"""Testes para as rotas da API REST."""

from datetime import date, timedelta

import pytest

from app.models.contratacoes import Contratacao, Contrato, Fornecedor, Orgao


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────


async def _seed_orgao(db):
    orgao = Orgao(cnpj="99000000000100", razao_social="ORGAO TESTE", esfera="M", uf="BA")
    db.add(orgao)
    await db.flush()
    return orgao


async def _seed_fornecedor(db):
    f = Fornecedor(cpf_cnpj="88000000000100", nome="EMPRESA TESTE LTDA", tipo="PJ")
    db.add(f)
    await db.flush()
    return f


async def _seed_contratacao(db, orgao, **overrides):
    campos = {
        "pncp_id": "99000000000100-1-000999/2025",
        "ano": 2025,
        "modalidade": "Pregão - Eletrônico",
        "objeto": "Aquisição de equipamentos",
        "valor_estimado": 100000,
        "situacao": "Homologada",
        "data_publicacao": date(2025, 3, 15),
        "fonte": "pncp",
        "orgao_id": orgao.id,
    }
    campos.update(overrides)
    c = Contratacao(**campos)
    db.add(c)
    await db.flush()
    return c


async def _seed_contrato(db, fornecedor, contratacao=None, **overrides):
    campos = {
        "pncp_id": "99000000000100-2-000999/2025",
        "numero_contrato": "CONTRATO TEST-001/2025",
        "ano": 2025,
        "objeto": "Fornecimento de computadores (TESTE)",
        "valor_inicial": 142000,
        "data_assinatura": date(2025, 4, 1),
        "data_inicio_vigencia": date(2025, 4, 1),
        "data_fim_vigencia": date(2026, 4, 1),
        "fonte": "pncp",
        "fornecedor_id": fornecedor.id,
        "contratacao_id": contratacao.id if contratacao else None,
    }
    campos.update(overrides)
    c = Contrato(**campos)
    db.add(c)
    await db.flush()
    return c


# ──────────────────────────────────────────
# Órgãos
# ──────────────────────────────────────────


class TestOrgaos:
    async def test_listar_orgaos_busca_sem_resultado(self, client):
        """Busca por termo inexistente retorna lista vazia."""
        r = await client.get("/api/v1/orgaos/", params={"busca": "ZZZZINEXISTENTE"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["dados"] == []

    async def test_listar_orgaos_com_dado(self, client, db_session):
        await _seed_orgao(db_session)
        await db_session.flush()

        r = await client.get("/api/v1/orgaos/", params={"busca": "ORGAO TESTE"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        assert any(o["cnpj"] == "99000000000100" for o in r.json()["dados"])

    async def test_busca_orgao(self, client, db_session):
        await _seed_orgao(db_session)
        await db_session.flush()

        r = await client.get("/api/v1/orgaos/", params={"busca": "ORGAO TESTE"})
        assert r.json()["total"] >= 1

        r = await client.get("/api/v1/orgaos/", params={"busca": "ZZZZINEXISTENTE999"})
        assert r.json()["total"] == 0

    async def test_orgao_404(self, client):
        r = await client.get("/api/v1/orgaos/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ──────────────────────────────────────────
# Contratações
# ──────────────────────────────────────────


class TestContratacoes:
    async def test_listar_contratacoes(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        await _seed_contratacao(db_session, orgao)
        await db_session.flush()

        r = await client.get("/api/v1/contratacoes/", params={"busca": "TESTE"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_filtrar_por_ano(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        await _seed_contratacao(db_session, orgao, ano=2099, pncp_id="test-yr-a", objeto="Teste ano A")
        await _seed_contratacao(db_session, orgao, ano=2098, pncp_id="test-yr-b", objeto="Teste ano B")
        await db_session.flush()

        r = await client.get("/api/v1/contratacoes/", params={"ano": 2099})
        assert r.json()["total"] == 1

    async def test_filtrar_por_modalidade(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        await _seed_contratacao(db_session, orgao, modalidade="TestModalidade", pncp_id="test-mod-c")
        await _seed_contratacao(db_session, orgao, modalidade="OutraTestMod", pncp_id="test-mod-d")
        await db_session.flush()

        r = await client.get("/api/v1/contratacoes/", params={"modalidade": "TestModalidade"})
        assert r.json()["total"] == 1

    async def test_busca_objeto(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        await _seed_contratacao(db_session, orgao, objeto="Reforma ZZUNICO do prédio")
        await db_session.flush()

        r = await client.get("/api/v1/contratacoes/", params={"busca": "ZZUNICO"})
        assert r.json()["total"] == 1

    async def test_detalhe_com_contratos(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        fornecedor = await _seed_fornecedor(db_session)
        contratacao = await _seed_contratacao(db_session, orgao)
        await _seed_contrato(db_session, fornecedor, contratacao)
        await db_session.flush()

        r = await client.get(f"/api/v1/contratacoes/{contratacao.id}")
        assert r.status_code == 200
        data = r.json()
        assert len(data["contratos"]) == 1


# ──────────────────────────────────────────
# Contratos
# ──────────────────────────────────────────


class TestContratos:
    async def test_listar_contratos(self, client, db_session):
        fornecedor = await _seed_fornecedor(db_session)
        await _seed_contrato(db_session, fornecedor)
        await db_session.flush()

        r = await client.get("/api/v1/contratos/", params={"busca": "TESTE"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_contratos_vencendo(self, client, db_session):
        fornecedor = await _seed_fornecedor(db_session)

        # Vence em 15 dias
        await _seed_contrato(
            db_session, fornecedor,
            pncp_id="test-venc-1",
            data_fim_vigencia=date.today() + timedelta(days=15),
        )
        # Vence em 60 dias
        await _seed_contrato(
            db_session, fornecedor,
            pncp_id="test-venc-2",
            data_fim_vigencia=date.today() + timedelta(days=60),
        )
        # Já venceu
        await _seed_contrato(
            db_session, fornecedor,
            pncp_id="test-venc-3",
            data_fim_vigencia=date.today() - timedelta(days=10),
        )
        await db_session.flush()

        r = await client.get("/api/v1/contratos/vencendo", params={"dias": 30})
        assert r.json()["total"] >= 1

        r = await client.get("/api/v1/contratos/vencendo", params={"dias": 90})
        assert r.json()["total"] >= 2

    async def test_detalhe_contrato_com_relacoes(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        fornecedor = await _seed_fornecedor(db_session)
        contratacao = await _seed_contratacao(db_session, orgao)
        contrato = await _seed_contrato(db_session, fornecedor, contratacao)
        await db_session.flush()

        r = await client.get(f"/api/v1/contratos/{contrato.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["fornecedor"]["nome"] == "EMPRESA TESTE LTDA"
        assert data["contratacao"]["pncp_id"] == "99000000000100-1-000999/2025"

    async def test_contrato_404(self, client):
        r = await client.get("/api/v1/contratos/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404


# ──────────────────────────────────────────
# Paginação
# ──────────────────────────────────────────


class TestPaginacao:
    async def test_paginacao_params(self, client, db_session):
        orgao = await _seed_orgao(db_session)
        for i in range(5):
            await _seed_contratacao(db_session, orgao, pncp_id=f"pagtest-{i}", objeto=f"PAGTEST item {i}")
        await db_session.flush()

        r = await client.get("/api/v1/contratacoes/", params={"pagina": 1, "tamanho_pagina": 2, "busca": "PAGTEST"})
        data = r.json()
        assert data["total"] == 5
        assert len(data["dados"]) == 2
        assert data["pagina"] == 1

        r = await client.get("/api/v1/contratacoes/", params={"pagina": 3, "tamanho_pagina": 2, "busca": "PAGTEST"})
        assert len(r.json()["dados"]) == 1
