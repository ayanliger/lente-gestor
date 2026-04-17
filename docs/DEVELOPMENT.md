# Guia de Desenvolvimento

## Setup Inicial

### 1. Pré-requisitos

- Python 3.12+
- Node.js 20+ (para o frontend, quando inicializado)
- Docker e Docker Compose
- Git
- Google Cloud SDK (`gcloud`) — para autenticação Vertex AI (RAG)

### 2. Clone e Configuração

```bash
git clone https://github.com/ayanliger/lente-gestor.git
cd lente-gestor

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com GCP_PROJECT_ID e demais configurações
```

### 3. Banco de Dados

```bash
# Subir PostgreSQL + pgvector
make db

# Verificar se está rodando
docker compose ps
```

### 4. Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
pip install -e ".[dev]"  # inclui pytest, ruff, mypy

# Aplicar migrações do banco
PYTHONPATH=. alembic upgrade head

# Rodar servidor
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API disponível em `http://localhost:8000`
Swagger interativo em `http://localhost:8000/docs`

### 5. Ingestão de Dados (PNCP)

```bash
cd backend

# Ingestão completa (último ano até hoje)
PYTHONPATH=. python -m scripts.ingest_pncp

# Período específico
PYTHONPATH=. python -m scripts.ingest_pncp --desde 2025-01-01 --ate 2025-06-01

# Via Makefile (da raiz do projeto)
make ingest-pncp
```

A ingestão busca contratações (por modalidade) e contratos do PNCP para Jequié,
normalizando e persistindo via upsert. Re-execuções atualizam registros existentes.

### 6. Autenticação Google Cloud (para RAG)

```bash
gcloud auth application-default login
```

Isso gera credenciais locais que o SDK `google-genai` usa automaticamente.

## Convenções

### Estrutura de Código

```
backend/app/
├── api/routes/      # Endpoints REST — cada arquivo = um recurso
├── connectors/      # Clientes para APIs externas (PNCP, TCM-BA, etc.)
├── models/          # SQLAlchemy models — cada arquivo = um domínio
├── services/        # Lógica de negócio — cruzamentos, indicadores, RAG
├── db/              # Configuração do banco, migrações
├── config.py        # Settings via Pydantic
└── main.py          # Entrypoint FastAPI
```

### Padrões

- **Async everywhere**: FastAPI + SQLAlchemy async + httpx async
- **Type hints**: obrigatório em todas as funções públicas
- **Docstrings**: em português, em todas as classes e funções públicas
- **Logging**: usar `structlog` com contexto estruturado
- **Erros**: nunca silenciar exceções; logar e re-raise ou tratar

### Git

- Branch principal: `main`
- Feature branches: `feat/<descrição-curta>`
- Fix branches: `fix/<descrição-curta>`
- Commits em português, formato: `tipo: descrição`
  - `feat: adicionar conector PNCP`
  - `fix: corrigir paginação de contratos`
  - `docs: atualizar README com instruções de deploy`
  - `refactor: extrair lógica de cruzamento para service`

### Migrações

```bash
# Criar nova migração após alterar modelos
make migrate-new msg="adicionar tabela fornecedores"

# Aplicar migrações
make migrate
```

### Testes

```bash
# Rodar todos os testes (requer PostgreSQL rodando)
cd backend && PYTHONPATH=. pytest -v

# Rodar com cobertura
cd backend && PYTHONPATH=. pytest --cov=app --cov-report=html

# Via Makefile
make test
```

Os testes usam o mesmo banco de desenvolvimento com isolamento por transação
(rollback automático). Fixtures de teste usam CNPJs próprios (`99000000000100`)
para não conflitar com dados reais ingeridos.

## Comandos Úteis

| Comando | Descrição |
|---------|-----------|
| `make help` | Lista todos os comandos disponíveis |
| `make dev` | Servidor de desenvolvimento |
| `make db` | Sobe PostgreSQL |
| `make db-stop` | Para PostgreSQL |
| `make db-reset` | Reseta banco (apaga tudo) |
| `make migrate` | Aplica migrações |
| `make test` | Executa testes |
| `make lint` | Verifica estilo |
|| `make format` | Formata código |
|| `make ingest-pncp` | Ingere dados do PNCP |

## Fontes de Dados — Referência Rápida

### PNCP API

- Base URL: `https://pncp.gov.br/api/consulta/v1/`
- Swagger: `https://pncp.gov.br/api/consulta/swagger-ui/index.html`
- Sem autenticação
- CNPJ Jequié: `13894878000160`

### Teste rápido da API

```bash
# Contratações de Jequié (dispensa, modalidade 8)
curl 'https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20250101&dataFinal=20250601&codigoModalidadeContratacao=8&cnpj=13894878000160&pagina=1&tamanhoPagina=10'

# Contratos de Jequié (max 365 dias)
curl 'https://pncp.gov.br/api/consulta/v1/contratos?dataInicial=20250101&dataFinal=20250601&cnpjOrgao=13894878000160&pagina=1&tamanhoPagina=10'
```

### Endpoints da API local

Após ingestão, com o servidor rodando:

```bash
curl http://localhost:8000/api/v1/contratacoes/
curl http://localhost:8000/api/v1/contratos/
curl 'http://localhost:8000/api/v1/contratos/vencendo?dias=90'
curl http://localhost:8000/api/v1/fornecedores/
curl http://localhost:8000/api/v1/orgaos/
curl http://localhost:8000/api/v1/pca/
```
