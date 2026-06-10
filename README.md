# Lente Gestor

> **Lente** - Ferramenta de inteligência, cruzamento de dados e accountability para a administração pública municipal.

![Status](https://img.shields.io/badge/status-pausado-orange)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL%2016-pgvector-4169E1?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-83%20passing-success)
![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform&logoColor=white)
![GCP](https://img.shields.io/badge/GCP-Cloud%20Run%20%2B%20Cloud%20SQL-4285F4?logo=googlecloud&logoColor=white)

> [!NOTE]
> **⏸️ Projeto em pausa (junho/2026).** O protótipo foi construído e implantado
> com dados reais, mas o desenvolvimento está atualmente dormente e a infraestrutura
> em nuvem foi pausada para cortar custos. O código foi aberto sob licença MIT
> como referência e portfólio. O estado da infraestrutura e os passos para
> retomar estão documentados em [`infra/README.md`](infra/README.md).
> O projeto roda integralmente em ambiente local (ver [Quickstart](#quickstart)).

---

## Visão Geral

Plataforma digital que funciona como **camada de inteligência sobre dados públicos municipais**. A **Lente** permite ao gestor:

- **Cruzar dados** de múltiplas fontes (PNCP, SICONFI, IBGE, portal de transparência) em uma visão unificada
- **Detectar inconsistências** proativamente - concentração de fornecedores, desvios orçamentários, contratos vencendo sem renovação
- **Questionar com evidências** - assistente de IA (RAG com Gemini) que responde em linguagem natural com rastreabilidade total até a fonte

**Município-piloto:** Jequié - BA (~150 mil habitantes)

## Status do Projeto

| Marco | Status |
|-------|--------|
| Schema do banco + migrações Alembic | ✅ Implementado |
| API REST (FastAPI) | ✅ Implementado |
| Pipeline de ingestão PNCP | ✅ Implementado |
| Conector SICONFI (RREO/RGF/DCA) | ✅ Implementado |
| Conector IBGE (população + PIB municipal) | ✅ Implementado |
| Indicadores LRF + mínimos constitucionais | ✅ Implementado |
| Painel de Arrecadação Tributária (Município Online) | ✅ Implementado |
| Frontend React (painel orçamento-first + LRF) | ✅ Implementado |
| Camada RAG (Gemini + pgvector) | ✅ Fase 1 implementada |
| Testes automatizados (backend) | ✅ 83 testes passando |
| Deploy em Google Cloud (Cloud Run + Cloud SQL) | ⏸️ Implantado, pausado em jun/2026 |
| Estratégia de entrada (CPSI) | ⏸️ Negociações estagnadas |
| Conectores Portal Transparência + TCM-BA | 📋 Não iniciado |

## Infraestrutura em Nuvem (pausada)

O stack completo foi provisionado via Terraform no projeto GCP `lente-gestor`
(us-central1) e está atualmente **pausado**:

- **Cloud Run service** `lente-api` - acesso público removido (retorna 403)
- **Cloud SQL** `lente-db` (PostgreSQL 16 + pgvector) - instância parada, dados preservados
- **Cloud Run Jobs** - `migrate-db`, `ingest-pncp`, `ingest-orcamento`, `ingest-rgf`, `ingest-ibge`, `ingest-rag` (inertes, só cobram quando executados)
- **Frontend** (Firebase Hosting) - https://lente-gestor.web.app segue no ar, mas sem API por trás

Detalhes da pausa, custo residual (~US$2-4/mês) e comandos para retomar:
[`infra/README.md`](infra/README.md).

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
| **Infra** | Docker, Docker Compose, Terraform, Google Cloud (Cloud Run, Cloud SQL, Secret Manager, Artifact Registry) |

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
│   │   │   ├── ingestao_orcamento.py  # RREO -> ExecucaoOrcamentaria
│   │   │   ├── ingestao_ibge.py       # População + PIB -> DadosMunicipio
│   │   │   └── indicadores_fiscais.py # RGF -> IndicadorFiscal (LRF + mínimos)
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
│   ├── vite.config.ts            # Proxy /api -> backend
│   └── package.json
├── infra/                        # Terraform: Cloud Run, Cloud SQL, secrets, jobs
├── scripts/
│   └── init-db.sql               # pgvector + unaccent + uuid-ossp
├── data/                         # Dados locais (não versionado)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_SOURCES.md
│   ├── DEVELOPMENT.md
│   └── EXTENSAO_ORCAMENTO.md     # Plano da camada orçamentária (Fases 1-5)
├── cloudbuild.yaml               # Build + deploy via Cloud Build
├── docker-compose.yml            # PostgreSQL + pgvector
├── Makefile                      # make dev, db, migrate, test, ingest-*, ...
├── .env.example
└── README.md
```

## Pré-requisitos

- Python 3.12+
- Node.js 20+ (para o frontend)
- Docker e Docker Compose
- (Opcional, só para a camada RAG) Projeto Google Cloud com Vertex AI habilitado
  e `gcloud` CLI autenticado (`gcloud auth application-default login`)

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

- **Backend**: http://localhost:8000 - Swagger em /docs
- **Frontend**: http://localhost:5173 - proxy automático de /api -> backend

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
| `GET /municipio/dados` | Dados contextuais do IBGE (população, PIB, PIB per capita) - série histórica ou por exercício |

**Assistente conversacional (RAG - Fase 1)**

| Endpoint | Descrição |
|----------|----------|
| `POST /chat/` | Pergunta em linguagem natural sobre orçamento, LRF, PCA e contratos. Resposta com citações obrigatórias por índice `[n]` e recusa explícita (`recusou=true`) quando o corpus não respalda a resposta. Rate limit de cortesia: 20 req/min por IP (`slowapi`). |

### Pipeline de Ingestão

Quatro pipelines assíncronos com retry exponencial, paginação automática e preservação do JSON bruto para auditoria:

- **PNCP** - contratações, contratos e PCA; upsert de órgãos e fornecedores por CNPJ; vinculação contratação <-> contrato via `numeroControlePncpCompra`
- **SICONFI RREO** - ingestão bimestral da execução orçamentária em `ExecucaoOrcamentaria` (formato longo espelhando 1:1 a API do Tesouro, conforme ADR em `docs/EXTENSAO_ORCAMENTO.md`)
- **SICONFI RGF** - derivação dos 7 indicadores principais da LRF + mínimos de saúde/educação; cálculo de situação (`OK`/`ALERTA`/`EXCEDIDO`/`ABAIXO_MINIMO`) ainda na ingestão
- **IBGE** - metadados do município, série de população estimada (SIDRA 6579) e PIB municipal (SIDRA 5938)

### Frontend (React)

Layout com navegação agrupada: **Orçamento** como seção primária (heading em âmbar) e **Contratos & Aquisições** como grupo secundário (tipografia menor, após divisor).

- **Visão Geral** - painel orçamento-first com seletor de exercício/bimestre, hero com dotação/empenhado/% execução (tom da cor acompanha a situação), composição da despesa por função em barras gradiente, resumo da situação fiscal (cards LRF), painel consolidado de alertas (EXCEDIDO / ABAIXO_MINIMO / ALERTA + contratos vencendo) e faixa secundária de contratos
- **Execução** - execução detalhada por função de governo (RREO-Anexo 02): gráfico comparativo dotação x empenhado e tabela com % de execução por função
- **Indicadores LRF** - cards por indicador com termômetro animado, marcador de alerta a 90%, faixa de excesso listrada e referência legal (LRF / CF)
- **Assistente** - chat com citações clicáveis que abrem drawer lateral com metadados e link para a página de origem do documento; recusa em vez de alucinar quando o dado não está indexado
- **Contratações** - tabela paginada com busca por objeto e badges de modalidade
- **Contratos** - tabela paginada com destaque visual para vencimentos em 90 dias
- **Fornecedores** - busca por nome/CNPJ, badges PF/PJ

## Comandos Úteis

```bash
make db                        # Sobe PostgreSQL + pgvector
make dev                       # Servidor backend em modo reload
make migrate                   # Aplica migrações pendentes
make migrate-new msg="..."     # Nova migração a partir dos modelos
make ingest-pncp               # Ingestão PNCP + auto-reindex RAG (CONTRATO, RESUMO_PCA)
make ingest-orcamento ano=AAAA # RREO/SICONFI + auto-reindex (RESUMO_FUNCAO)
make ingest-orcamento-historico     # Backfill RREO plurianual 2020-2026
make ingest-rgf ano=AAAA       # RGF/SICONFI + indicadores + auto-reindex (INDICADOR_FISCAL)
make ingest-rgf-historico           # Backfill RGF plurianual 2020-2025
make ingest-ibge               # Dados contextuais do IBGE
make ingest-arrecadacao ano=AAAA # Arrecadação tributária de um exercício (Município Online)
make ingest-arrecadacao-historico   # Backfill plurianual 2020-2026 (agregado, sem drill-down)
make ingest-rag                # Reindexação RAG completa (rebuild manual)
make test                      # Testes unitários (sem rede)
make test-integration          # Testes contra Vertex AI (consome créditos GCP)
make lint                      # ruff check
make format                    # ruff format
```

## Fontes de Dados

| Fonte | Método | Status |
|-------|--------|--------|
| **PNCP** - Contratações, contratos, PCA, atas, NF-e | API REST pública | ✅ Ingerido |
| **SICONFI** - RREO, RGF, DCA (Tesouro Nacional) | API REST pública (ORDS) | ✅ Ingerido |
| **IBGE** - População, PIB, metadados municipais | APIs SIDRA + localidades | ✅ Ingerido |
| **Município Online** - Arrecadação tributária (mensal, histórica 2020-2026; drill-down por banco opcional) | Scraping estruturado (ASP.NET postback + drill-down JSON) | ✅ Ingerido |
| **Portal Transparência Jequié** - Empenhos detalhados, folha | Scraping / acesso direto | 📋 Não iniciado |
| **TCM-BA** - Obras, publicidade, SICOB, SIES | Portal público | 📋 Não iniciado |

Detalhes em [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md). Para a camada orçamentária ver [`docs/EXTENSAO_ORCAMENTO.md`](docs/EXTENSAO_ORCAMENTO.md).

## O Que Ficaria Por Fazer

Se o projeto for retomado, as frentes pendentes são:

- **Conectores adicionais** - Portal de Transparência de Jequié (empenhos individuais, folha detalhada) e TCM-BA (SICOB obras, SIP publicidade, SAPPE pessoal, SIES educação/saúde)
- **RAG Fases 2+** - avaliação com conjunto dourado de perguntas (recall, precisão de citação, taxa de recusa apropriada), histórico de conversa em sessão
- **CI/CD** - esteira GitHub Actions com `terraform plan`/`apply` separados por ambiente e ingestões agendadas via Cloud Scheduler
- **Observabilidade** - dashboards de SLO e alertas de falha de ingestão no Cloud Monitoring

## Contexto Comercial (histórico)

O modelo de entrada previsto era contratação via **CPSI** (Contratação Pública
de Solução Inovadora - LC 182/2021): contrato de 12 meses prorrogável, sem
especificação técnica prévia, com possibilidade de contratação definitiva após
validação (art. 15). As negociações com o município-piloto estagnaram e o
projeto foi pausado antes da assinatura.

## Princípios de Desenvolvimento

1. **Rastreabilidade total** - Toda resposta da IA cita a fonte. Sem fonte = sem resposta.
2. **Dados reais desde o dia zero** - Protótipo construído com dados reais de Jequié, não mocks.
3. **Complementar, não substituto** - A Lente não compete com ERPs; consome seus dados.
4. **Accountability, não visualização** - O valor não é o gráfico; é a capacidade de questionar com evidências.

## Licença

[MIT](LICENSE) - sinta-se à vontade para estudar, reusar e adaptar.
