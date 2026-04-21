# Lente Gestor

> **Lente** — Ferramenta de inteligência, cruzamento de dados e accountability para a administração pública municipal.

---

## Visão Geral

Plataforma digital que funciona como **camada de inteligência sobre dados públicos municipais**. A **Lente** permite ao gestor:

- **Cruzar dados** de múltiplas fontes (PNCP, portal de transparência, TCM-BA) em uma visão unificada
- **Detectar inconsistências** proativamente — concentração de fornecedores, desvios orçamentários, contratos vencendo sem renovação
- **Questionar com evidências** — assistente de IA (RAG com Gemini) que responde em linguagem natural com rastreabilidade total até a fonte

**Município-piloto:** Jequié — BA (~150 mil habitantes)
## Deploy Público (Protótipo)
| Componente | URL |
|------------|-----|
| **Frontend** | https://lente-gestor.web.app |
| **API** | https://lente-api-tguspcnbeq-uc.a.run.app |
| **Swagger** | https://lente-api-tguspcnbeq-uc.a.run.app/docs |
O frontend público usa `rewrites` do Firebase Hosting para proxy transparente
de `/api/**` → Cloud Run. Infraestrutura completa documentada em [`infra/README.md`](infra/README.md).
- **Projeto GCP:** `lente-gestor` (us-central1)
- **Cloud SQL:** `lente-db` (PostgreSQL 16 + pgvector)
- **Cloud Run service:** `lente-api` (público, escala a zero)
- **Cloud Run Jobs:** `migrate-db`, `ingest-pncp`, `ingest-orcamento`, `ingest-rgf`, `ingest-ibge`, `ingest-rag`

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
| Conector SICONFI (RREO/RGF/DCA) | ✅ Implementado |
| Conector IBGE (população + PIB municipal) | ✅ Implementado |
| Indicadores LRF + mínimos constitucionais | ✅ Implementado |
| Frontend React (painel orçamento-first + LRF) | ✅ Implementado |
| Testes automatizados (backend) | ✅ 83 testes passando |
| Deploy em Google Cloud (Cloud Run + Cloud SQL) | ✅ No ar |
| Camada RAG (Gemini + pgvector) | 🟡 Fase 1 implementada |
| Painel de Arrecadação Tributária (Município Online) | ✅ Implementado |
| Conectores Portal Transparência + TCM-BA | 📋 Roadmap |

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
| **Testes** | pytest + pytest-asyncio, 83 testes cobrindo conectores, ingestão e rotas |
| **Infra** | Docker, Docker Compose, Google Cloud (Cloud Run, Cloud SQL) |

## Estrutura do Repositório

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/           # contratacoes, contratos, fornecedores, orgaos,
│   │   │   │                     # itens_pca, orcamento, municipio
│   │   │   ├── deps.py           # Dependências (DB session, etc.)
│   │   │   └── schemas.py        # Schemas Pydantic
│   │   ├── connectors/
│   │   │   ├── pncp.py           # Cliente async PNCP
│   │   │   ├── siconfi.py        # Cliente async SICONFI (RREO/RGF/DCA)
│   │   │   └── ibge.py           # Cliente async IBGE (SIDRA + localidades)
│   │   ├── db/
│   │   │   ├── migrations/       # Migrações Alembic
│   │   │   └── session.py        # Engine e sessão SQLAlchemy async
│   │   ├── models/
│   │   │   ├── contratacoes.py   # Orgao, Fornecedor, Contratacao, Contrato, ItemPCA
│   │   │   └── orcamento.py      # ExecucaoOrcamentaria, IndicadorFiscal, DadosMunicipio
│   │   ├── services/
│   │   │   ├── ingestao_pncp.py       # Normalização + upsert PNCP
│   │   │   ├── ingestao_orcamento.py  # RREO → ExecucaoOrcamentaria
│   │   │   ├── ingestao_ibge.py       # População + PIB → DadosMunicipio
│   │   │   └── indicadores_fiscais.py # RGF → IndicadorFiscal (LRF + mínimos)
│   │   ├── config.py
│   │   └── main.py
│   ├── scripts/
│   │   ├── ingest_pncp.py        # make ingest-pncp
│   │   ├── ingest_orcamento.py   # make ingest-orcamento ano=YYYY
│   │   ├── ingest_ibge.py        # make ingest-ibge
│   │   └── ingest_rgf.py         # make ingest-rgf ano=YYYY
│   ├── tests/                    # 83 testes (conectores, ingestão, rotas)
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                  # Cliente Axios, tipos, hooks React Query
│   │   ├── components/           # Layout (nav agrupada), ComposicaoBar,
│   │   │                         # Termometro, Pagination, SearchInput, TableSkeleton
│   │   ├── pages/                # Dashboard (orçamento-first), Orcamento,
│   │   │                         # IndicadoresLRF, Contratacoes, Contratos, Fornecedores
│   │   ├── lib/                  # Utilitários (format BRL, datas)
│   │   ├── App.tsx               # Rotas
│   │   ├── main.tsx              # Entry (React Query + Router)
│   │   └── index.css             # TailwindCSS + design tokens lente
│   ├── vite.config.ts            # Proxy /api → backend
│   └── package.json
├── scripts/
│   └── init-db.sql               # pgvector + unaccent + uuid-ossp
├── data/                         # Dados locais (não versionado)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_SOURCES.md
│   ├── DEVELOPMENT.md
│   └── EXTENSAO_ORCAMENTO.md     # Plano da camada orçamentária (Fases 1-5)
├── docker-compose.yml            # PostgreSQL + pgvector
├── Makefile                      # make dev, db, migrate, test, ingest-*, ...
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

# 6. (Opcional) Ingestão de dados reais de Jequié
PYTHONPATH=. python -m scripts.ingest_pncp --desde 2025-01-01 --ate 2025-06-01
PYTHONPATH=. python -m scripts.ingest_orcamento --exercicio 2024
PYTHONPATH=. python -m scripts.ingest_rgf --exercicio 2024
PYTHONPATH=. python -m scripts.ingest_ibge

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

API REST sob `/api/v1` com paginação, busca e filtros.

**Contratos e aquisições (PNCP)**

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

**Orçamento e indicadores fiscais (SICONFI + IBGE)**

| Endpoint | Descrição |
|----------|----------|
| `GET /orcamento/execucao` | Células brutas do RREO/RGF com filtros (exercício, período, anexo, conta) |
| `GET /orcamento/resumo-por-funcao` | Execução por função pivoteada: dotação inicial/atualizada, empenhado, liquidado, saldo |
| `GET /orcamento/indicadores` | Indicadores LRF + mínimos constitucionais com situação derivada e limite legal |
| `GET /municipio/dados` | Dados contextuais do IBGE (população, PIB, PIB per capita) — série histórica ou por exercício |

**Assistente conversacional (RAG — Fase 1)**

| Endpoint | Descrição |
|----------|----------|
| `POST /chat/` | Pergunta em linguagem natural sobre orçamento, LRF, PCA e contratos. Resposta com citações obrigatórias por índice `[n]` e recusa explícita (`recusou=true`) quando o corpus não respalda a resposta. Rate limit de cortesia: 20 req/min por IP (`slowapi`). |

### Pipeline de Ingestão

Quatro pipelines assíncronos com retry exponencial, paginação automática e preservação do JSON bruto para auditoria:

- **PNCP** — contratações, contratos e PCA; upsert de órgãos e fornecedores por CNPJ; vinculação contratação ↔ contrato via `numeroControlePncpCompra`
- **SICONFI RREO** — ingestão bimestral da execução orçamentária em `ExecucaoOrcamentaria` (formato longo espelhando 1:1 a API do Tesouro, conforme ADR em `docs/EXTENSAO_ORCAMENTO.md`)
- **SICONFI RGF** — derivação dos 7 indicadores principais da LRF + mínimos de saúde/educação; cálculo de situação (`OK`/`ALERTA`/`EXCEDIDO`/`ABAIXO_MINIMO`) ainda na ingestão
- **IBGE** — metadados do município, série de população estimada (SIDRA 6579) e PIB municipal (SIDRA 5938)

### Frontend (React)

Layout com navegação agrupada: **Orçamento** como seção primária (heading em âmbar) e **Contratos & Aquisições** como grupo secundário (tipografia menor, após divisor).

- **Visão Geral** — painel orçamento-first com seletor de exercício/bimestre, hero com dotação/empenhado/% execução (tom da cor acompanha a situação), composição da despesa por função em barras gradiente, resumo da situação fiscal (cards LRF), painel consolidado de alertas (EXCEDIDO / ABAIXO_MINIMO / ALERTA + contratos vencendo) e faixa secundária de contratos
- **Execução** — execução detalhada por função de governo (RREO-Anexo 02): gráfico comparativo dotação × empenhado e tabela com % de execução por função
- **Indicadores LRF** — cards por indicador com termômetro animado, marcador de alerta a 90%, faixa de excesso listrada e referência legal (LRF / CF)
- **Assistente** — chat com citações clicáveis que abrem drawer lateral com metadados e link para a página de origem do documento; recusa em vez de alucinar quando o dado não está indexado
- **Contratações** — tabela paginada com busca por objeto e badges de modalidade
- **Contratos** — tabela paginada com destaque visual para vencimentos em 90 dias
- **Fornecedores** — busca por nome/CNPJ, badges PF/PJ

## Comandos Úteis

```bash
make db                        # Sobe PostgreSQL + pgvector
make dev                       # Servidor backend em modo reload
make migrate                   # Aplica migrações pendentes
make migrate-new msg="..."     # Nova migração a partir dos modelos
make ingest-pncp               # Ingestão PNCP + auto-reindex RAG (CONTRATO, RESUMO_PCA)
make ingest-orcamento ano=AAAA # RREO/SICONFI + auto-reindex (RESUMO_FUNCAO)
make ingest-rgf ano=AAAA       # RGF/SICONFI + indicadores + auto-reindex (INDICADOR_FISCAL)
make ingest-ibge               # Dados contextuais do IBGE
make ingest-arrecadacao ano=AAAA # Arrecadação tributária (Município Online) + drill-down por banco
make ingest-rag                # Reindexação RAG completa (rebuild manual)
make test                      # Testes unitários (sem rede)
make test-integration          # Testes contra Vertex AI (consome créditos GCP)
make lint                      # ruff check
make format                    # ruff format
```

## Fontes de Dados

| Fonte | Método | Status |
|-------|--------|--------|
| **PNCP** — Contratações, contratos, PCA, atas, NF-e | API REST pública | ✅ Ingerido |
| **SICONFI** — RREO, RGF, DCA (Tesouro Nacional) | API REST pública (ORDS) | ✅ Ingerido |
| **IBGE** — População, PIB, metadados municipais | APIs SIDRA + localidades | ✅ Ingerido |
| **Município Online** — Arrecadação tributária (mensal + por banco recebedor) | Scraping estruturado (ASP.NET postback + drill-down JSON) | ✅ Ingerido |
| **Portal Transparência Jequié** — Empenhos detalhados, folha | Scraping / acesso direto | 📋 Roadmap |
| **TCM-BA** — Obras, publicidade, SICOB, SIES | Portal público | 📋 Roadmap |

Detalhes em [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md). Para a camada orçamentária ver [`docs/EXTENSAO_ORCAMENTO.md`](docs/EXTENSAO_ORCAMENTO.md).

## Roadmap

Com as camadas de dados (PNCP + SICONFI + IBGE) ingeridas e o painel orçamentário no frontend, as próximas frentes são **deploy gerenciado** e a **camada de IA/RAG** prometida pela Lente.

### Deploy em Google Cloud

| Componente | Serviço | Observações |
|------------|---------|-------------|
| Backend FastAPI | **Cloud Run** | Container stateless, escala a zero; build via Cloud Build a partir de `backend/Dockerfile` |
| Frontend React | **Cloud Run** (nginx servindo `dist/`) ou **Cloud Storage + CDN** | A decidir — depende da necessidade de SSR, hoje inexistente |
| Banco de dados | **Cloud SQL for PostgreSQL 16** | `pgvector` habilitado; conexão privada via VPC + Serverless VPC Access |
| Ingestão agendada | **Cloud Scheduler → Cloud Run Jobs** | Um job por fonte (`ingest_pncp`, `ingest_orcamento`, `ingest_rgf`, `ingest_ibge`) |
| Segredos | **Secret Manager** | `DATABASE_URL`, credenciais Vertex AI, tokens de terceiros |
| Infra como código | **Terraform** | Módulos separados para rede, banco, Cloud Run services e jobs |
| Observabilidade | **Cloud Logging + Cloud Monitoring** | `structlog` já emite JSON; alertas sobre falhas de ingestão |

Entregas previstas:

- `backend/Dockerfile` multi-stage (uv/pip + uvicorn) e `frontend/Dockerfile` (build Vite + nginx)
- Módulos Terraform em `infra/` + esteira de CI (GitHub Actions) com `plan`/`apply` separados por ambiente (dev, staging, prod)
- Cloud Run Jobs por ingestão, agendados via Cloud Scheduler com cron por fonte (PNCP diário; SICONFI bimestral/quadrimestral; IBGE anual)
- Migração Alembic rodando como Cloud Run Job pré-deploy
- Dashboards de SLO (disponibilidade da API, sucesso de ingestão) e alertas no Cloud Monitoring

### Camada RAG (Gemini + pgvector)

O diferencial estratégico da Lente: responder perguntas em linguagem natural com **rastreabilidade total até a fonte**. A infraestrutura já prevê `pgvector` (`scripts/init-db.sql`) e `gemini-embedding-2-preview` com `gemini-3.1-pro-preview` (`backend/app/config.py`).

Plano de implementação:

1. **Modelagem de documentos** — tabela `documentos_rag` com `conteudo_texto`, `embedding vector(3072)`, `fonte`, `referencia_id` e `metadados JSONB`. Um documento = um registro navegável (contrato, linha de RREO, indicador fiscal, etc.)
2. **Pipeline de indexação** — serviço `services/rag/indexador.py` que gera chunks + embeddings (Vertex AI) e faz upsert com `ON CONFLICT DO UPDATE` por `(fonte, referencia_id)`. Executado como Cloud Run Job após cada ingestão
3. **Recuperação híbrida** — `services/rag/recuperacao.py` combinando similaridade vetorial (`<=>` do pgvector) com filtro BM25/ILIKE por metadados. Top-K configurável com score mínimo
4. **Geração com citação** — `services/rag/gerador.py` usando Gemini 3.1 Pro via Vertex AI; prompt força citação explícita por afirmação (`[fonte:id]`) e recusa quando o contexto recuperado for insuficiente
5. **API conversacional** — `POST /api/v1/chat` com histórico em sessão e resposta acompanhada de `fontes_citadas[]` (cada uma com link direto para o registro de origem)
6. **Frontend** — componente de chat com citações clicáveis que abrem o registro de origem (contrato, célula orçamentária, indicador) em drawer lateral
7. **Avaliação** — conjunto dourado de perguntas do gestor com respostas esperadas; métricas de recall, precisão de citação e taxa de recusa apropriada

Princípio estrutural: **sem fonte, sem resposta**. O modelo é instruído a recusar quando os documentos recuperados não respaldam a afirmação, preservando accountability como valor central do produto.

### Conectores adicionais

Após GCP + RAG estabilizados, a cobertura de dados é estendida com:

- **Portal de Transparência de Jequié** — empenhos individuais, folha detalhada; complementa o SICONFI com granularidade por liquidação
- **TCM-BA** — SICOB (obras), SIP (publicidade), SAPPE (pessoal), SIES (educação/saúde)

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
