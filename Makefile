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

test: ## Executa testes
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

ingest-ibge: ## Ingestão de dados contextuais do IBGE (população, PIB)
	cd backend && python -m scripts.ingest_ibge

ingest-rgf: ## Ingestão do RGF/SICONFI + indicadores fiscais (uso: make ingest-rgf ano=2024)
	cd backend && python -m scripts.ingest_rgf --exercicio $(ano)

# ========================
# Limpeza
# ========================

clean: ## Remove arquivos temporários
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
