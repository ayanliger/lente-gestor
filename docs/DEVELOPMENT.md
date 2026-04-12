# Guia de Desenvolvimento

## Setup Inicial

### 1. Pré-requisitos

- Python 3.12+
- Node.js 20+ (para o frontend, quando inicializado)
- Docker e Docker Compose
- Git

### 2. Clone e Configuração

```bash
git clone <repo-url>
cd <repo-name>

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações (API keys, etc.)
```

### 3. Banco de Dados

```bash
# Subir PostgreSQL + pgvector
make db

# Verificar se está rodando
docker compose ps

# Criar tabelas (após configurar o Alembic)
make migrate
```

### 4. Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt
pip install -e ".[dev]"

# Rodar servidor
make dev
# ou: uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`
Docs interativos em `http://localhost:8000/docs`

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
# Rodar todos os testes
make test

# Rodar com cobertura
cd backend && pytest --cov=app --cov-report=html
```

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
| `make format` | Formata código |

## Fontes de Dados — Referência Rápida

### PNCP API

- Base URL: `https://pncp.gov.br/api/consulta/v1/`
- Swagger: `https://pncp.gov.br/api/consulta/swagger-ui/index.html`
- Sem autenticação
- CNPJ Jequié: `13894878000160`

### Teste rápido da API

```bash
# Listar contratações de Jequié em 2025
curl "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20250101&dataFinal=20250401&cnpjOrgao=13894878000160&pagina=1&tamanhoPagina=5" | python -m json.tool
```
