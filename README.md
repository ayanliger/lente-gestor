# Lente Gestor

> **Lente** — Ferramenta de inteligência, cruzamento de dados e accountability para a administração pública municipal.

---

## Visão Geral

Plataforma digital que funciona como **camada de inteligência sobre dados públicos municipais**. A **Lente** permite ao gestor:

- **Cruzar dados** de múltiplas fontes (PNCP, portal de transparência, TCM-BA) em uma visão unificada
- **Detectar inconsistências** proativamente — concentração de fornecedores, desvios orçamentários, contratos vencendo sem renovação
- **Questionar com evidências** — assistente de IA (RAG com Gemini) que responde em linguagem natural com rastreabilidade total até a fonte

**Município-piloto:** Jequié — BA (~150 mil habitantes)

## Status do Projeto

| Marco | Status |
|-------|--------|
| Validação de dados (PNCP API) | ✅ Confirmado |
| Validação de dados (Portal Transparência Local) | ✅ Ativo |
| Validação de dados (TCM-BA) | ✅ Ativo |
| Estratégia de entrada (CPSI) | 📋 Em articulação |
| Schema do banco + migrações Alembic | ✅ Implementado |
| API REST (FastAPI) | ✅ Implementado |
| Pipeline de ingestão PNCP | ✅ Implementado |
| Frontend React (dashboards base) | ✅ Implementado |
| Testes automatizados (backend) | ✅ 36 testes passando |
| Camada RAG (Gemini + pgvector) | 🔧 Em desenvolvimento |
| Conectores Portal Transparência + TCM-BA | 📋 Próximo |

## Arquitetura da Lente

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│              Dashboards · Alertas · Chat IA          │
├─────────────────────────────────────────────────────┤
│                  Backend (FastAPI)                    │
│          API REST · Autenticação · Regras            │
├──────────────┬──────────────┬───────────────────────┤
│  Ingestão    │  Analítica   │    IA / RAG           │
│  PNCP API    │  Cruzamentos │    pgvector           │
│  Scraping    │  Indicadores │    Gemini 3.1 Pro     │
│  Importação  │  Alertas     │    Rastreabilidade    │
├──────────────┴──────────────┴───────────────────────┤
│              PostgreSQL + pgvector                   │
│         Dados normalizados · Embeddings              │
└─────────────────────────────────────────────────────┘
```

Para detalhes, ver [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Stack Tecnológica

| Camada | Tecnologias |
|--------|-------------|
| **Frontend** | React 19 + TypeScript, Vite, TailwindCSS 4, React Router, TanStack Query, Axios, Recharts |
| **Backend** | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| **Banco de Dados** | PostgreSQL 16 + pgvector |
| **IA / RAG** | Gemini 3.1 Pro (Vertex AI), Gemini Embedding 2 (`gemini-embedding-2-preview`), pgvector |
| **Ingestão** | httpx (async), tenacity (retry), structlog, BeautifulSoup/lxml |
| **Testes** | pytest + pytest-asyncio, 36 testes cobrindo ingestão e rotas |
| **Infra** | Docker, Docker Compose, Google Cloud (Cloud Run, Cloud SQL) |

## Estrutura do Repositório

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/           # contratacoes, contratos, fornecedores, orgaos, pca
│   │   │   ├── deps.py           # Dependências (DB session, etc.)
│   │   │   └── schemas.py        # Schemas Pydantic
│   │   ├── connectors/
│   │   │   └── pncp.py           # Cliente async da API do PNCP
│   │   ├── db/
│   │   │   ├── migrations/       # Migrações Alembic
│   │   │   └── session.py        # Engine e sessão SQLAlchemy async
│   │   ├── models/
│   │   │   └── contratacoes.py   # Orgao, Fornecedor, Contratacao, Contrato, ItemPCA
│   │   ├── services/
│   │   │   └── ingestao_pncp.py  # Pipeline de ingestão (normalização + upsert)
│   │   ├── config.py
│   │   └── main.py
│   ├── scripts/
│   │   └── ingest_pncp.py        # CLI para ingestão (make ingest-pncp)
│   ├── tests/                    # 36 testes (ingestão + rotas)
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                  # Cliente Axios, tipos, hooks React Query
│   │   ├── components/           # Layout com sidebar
│   │   ├── pages/                # Dashboard, Contratações, Contratos, Fornecedores
│   │   ├── lib/                  # Utilitários (format BRL, datas)
│   │   ├── App.tsx               # Rotas
│   │   ├── main.tsx              # Entry (React Query + Router)
│   │   └── index.css             # TailwindCSS + design tokens
│   ├── vite.config.ts            # Proxy /api → backend
│   └── package.json
├── scripts/
│   └── init-db.sql               # pgvector + unaccent + uuid-ossp
├── data/                         # Dados locais (não versionado)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_SOURCES.md
│   └── DEVELOPMENT.md
├── docker-compose.yml            # PostgreSQL + pgvector
├── Makefile                      # make dev, db, migrate, test, ingest-pncp, ...
├── .env.example
└── README.md
```

## Pré-requisitos

- Python 3.12+
- Node.js 20+ (para o frontend)
- Docker e Docker Compose
- Projeto Google Cloud com Vertex AI habilitado (para a camada RAG)
- `gcloud` CLI autenticado (`gcloud auth application-default login`)

## Quickstart

```bash
# 1. Clone o repositório
git clone https://github.com/ayanliger/lente-gestor.git
cd lente-gestor

# 2. Copie e configure as variáveis de ambiente
cp .env.example .env
# Edite .env com GCP_PROJECT_ID e demais configurações

# 3. Suba o PostgreSQL + pgvector
docker compose up -d

# 4. Configure o backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

# 5. Execute as migrações
PYTHONPATH=. alembic upgrade head

# 6. (Opcional) Ingira dados reais do PNCP para Jequié
PYTHONPATH=. python -m scripts.ingest_pncp --desde 2025-01-01 --ate 2025-06-01

# 7. Inicie o servidor de desenvolvimento
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 8. (Em outro terminal) Inicie o frontend
cd frontend
npm install
npm run dev
```

- **Backend**: http://localhost:8000 — Swagger em /docs
- **Frontend**: http://localhost:5173 — proxy automático de /api → backend

## Funcionalidades Implementadas

### Backend (FastAPI)

API REST sob `/api/v1` com paginação, busca e filtros:

| Endpoint | Descrição |
|----------|----------|
| `GET /orgaos/` | Lista órgãos contratantes |
| `GET /fornecedores/` | Lista fornecedores (filtro por tipo PF/PJ) |
| `GET /contratacoes/` | Lista contratações (filtros: ano, modalidade, situação, órgão, data) |
| `GET /contratacoes/{id}` | Detalhe com contratos vinculados |
| `GET /contratos/` | Lista contratos (filtros: fornecedor, categoria, vigência) |
| `GET /contratos/vencendo?dias=N` | Contratos vencendo nos próximos N dias |
| `GET /contratos/{id}` | Detalhe com fornecedor e contratação |
| `GET /pca/` | Itens do Plano de Contratações Anual |

### Pipeline de Ingestão

Cliente async do PNCP com retry exponencial, paginação automática e normalização:

- Busca contratações por modalidade (Concorrência, Pregão, Inexigibilidade, Dispensa)
- Busca contratos firmados no período (respeita limite de 365 dias da API)
- Upsert de órgãos e fornecedores por CNPJ
- Vincula contratos à contratação de origem via `numeroControlePncpCompra`
- Preserva JSON bruto do PNCP para auditoria

### Frontend (React)

- **Dashboard**: KPIs (contratações, contratos, fornecedores, contratos vencendo) + tabela de contratos com vencimento próximo
- **Contratações**: tabela paginada com busca por objeto, badges de modalidade
- **Contratos**: tabela paginada com destaque visual para vencimentos próximos
- **Fornecedores**: busca por nome/CNPJ, badges PF/PJ

## Comandos Úteis

```bash
make db              # Sobe PostgreSQL + pgvector
make dev             # Servidor backend em modo reload
make migrate         # Aplica migrações pendentes
make migrate-new msg="..."  # Nova migração a partir dos modelos
make ingest-pncp     # Ingestão de dados do PNCP
make test            # Executa testes (36 testes)
make lint            # ruff check
make format          # ruff format
```

## Fontes de Dados

| Fonte | Método | Prioridade |
|-------|--------|------------|
| **PNCP** — Contratações, contratos, PCA, atas, NF-e | API REST pública | Máxima |
| **Portal Transparência Local** — Despesas, receitas, folha | Scraping / acesso direto | Alta |
| **TCM-BA** — Obras, publicidade, pessoal, educação/saúde | Portal público | Média |

Detalhes em [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Modelo de Entrada no Mercado

Contratação via **CPSI** (Contratação Pública de Solução Inovadora — LC 182/2021):
- Contrato de 12 meses, prorrogável por +12
- Sem especificação técnica prévia — define-se o problema, não a solução
- Art. 15 permite contratação definitiva após validação, sem nova licitação

## Princípios de Desenvolvimento

1. **Rastreabilidade total** — Toda resposta da IA cita a fonte. Sem fonte = sem resposta.
2. **Dados reais desde o dia zero** — Protótipo construído com dados reais de Jequié, não mocks.
3. **Complementar, não substituto** — A Lente não compete com ERPs; consome seus dados.
4. **Accountability, não visualização** — O valor não é o gráfico; é a capacidade de questionar com evidências.

## Equipe

| Papel | Foco |
|-------|------|
| **Técnico** | Arquitetura, desenvolvimento, IA/RAG |
| **Jurídico — Governança** | Articulação institucional, acesso à gestão municipal |
| **Jurídico — Contratações** | Marco regulatório, CPSI, estrutura societária |

## Licença

Repositório privado. Todos os direitos reservados.

---

*Documento de planejamento estratégico completo disponível em `/docs`.*
