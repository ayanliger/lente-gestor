.PHONY: help dev db db-stop migrate migrate-new test lint format clean

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========================
# Infraestrutura
# ========================

db: ## Sobe PostgreSQL + pgvector via Docker
	docker compose up -d
	@echo "Aguardando PostgreSQL..."
	@sleep 3
	@echo "PostgreSQL disponível em localhost:5432"

db-stop: ## Para o PostgreSQL
	docker compose down

db-reset: ## Reseta o banco (APAGA TUDO)
	docker compose down -v
	docker compose up -d
	@sleep 3
	cd backend && alembic upgrade head

# ========================
# Backend
# ========================

dev: ## Inicia o servidor de desenvolvimento
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate: ## Executa migrações pendentes
	cd backend && alembic upgrade head

migrate-new: ## Cria nova migração (uso: make migrate-new msg="descricao")
	cd backend && alembic revision --autogenerate -m "$(msg)"

# ========================
# Qualidade
# ========================

test: ## Executa testes unitários (sem integração com Vertex AI)
	cd backend && pytest -v -m "not integration"

test-integration: ## Executa testes com marker integration (consome créditos GCP)
	cd backend && pytest -v -m integration

test-all: ## Executa todos os testes (unitários + integração)
	cd backend && pytest -v

lint: ## Verifica estilo de código
	cd backend && ruff check .

format: ## Formata código automaticamente
	cd backend && ruff format .

# ========================
# Ingestão de Dados
# ========================

ingest-pncp: ## Executa ingestão de dados do PNCP
	cd backend && python -m scripts.ingest_pncp

ingest-orcamento: ## Ingestão do RREO/SICONFI (uso: make ingest-orcamento ano=2024)
	cd backend && python -m scripts.ingest_orcamento --exercicio $(ano)

ingest-orcamento-historico: ## Backfill RREO plurianual 2020–2026 (reindex RAG único ao final)
	cd backend && python -m scripts.ingest_orcamento --exercicios 2020 2021 2022 2023 2024 2025 2026

ingest-ibge: ## Ingestão de dados contextuais do IBGE (população, PIB)
	cd backend && python -m scripts.ingest_ibge

ingest-rgf: ## Ingestão do RGF/SICONFI + indicadores fiscais (uso: make ingest-rgf ano=2024)
	cd backend && python -m scripts.ingest_rgf --exercicio $(ano)

ingest-rgf-historico: ## Backfill RGF plurianual 2020–2025 + indicadores (reindex RAG único ao final)
	cd backend && python -m scripts.ingest_rgf --exercicios 2020 2021 2022 2023 2024 2025

ingest-arrecadacao: ## Ingestão da arrecadação tributária (uso: make ingest-arrecadacao ano=2025)
	cd backend && python -m scripts.ingest_arrecadacao --exercicio $(ano)

ingest-arrecadacao-historico: ## Backfill plurianual 2020–2026 (agregado, sem drill-down)
	cd backend && python -m scripts.ingest_arrecadacao --exercicios 2020 2021 2022 2023 2024 2025 2026

ingest-arrecadacao-dca: ## Arrecadação anual via SICONFI DCA (uso: make ingest-arrecadacao-dca ano=2020)
	cd backend && python -m scripts.ingest_arrecadacao_dca --exercicio $(ano)

ingest-arrecadacao-dca-historico: ## Backfill DCA 2020–2022 (cobre gap do Município Online)
	cd backend && python -m scripts.ingest_arrecadacao_dca --exercicios 2020 2021 2022

ingest-rag: ## Reindexação completa da base RAG (supõe ingestões de negócio já feitas)
	cd backend && python -m scripts.ingest_rag

# ========================
# Limpeza
# ========================

clean: ## Remove arquivos temporários
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
