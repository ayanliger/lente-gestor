# Lente Gestor

> **Lente** — Ferramenta de inteligência, cruzamento de dados e accountability para a administração pública municipal.

---

## Visão Geral

Plataforma digital que funciona como **camada de inteligência sobre dados públicos municipais**. A **Lente** permite ao gestor:

- **Cruzar dados** de múltiplas fontes (PNCP, portal de transparência, TCM-BA) em uma visão unificada
- **Detectar inconsistências** proativamente — concentração de fornecedores, desvios orçamentários, contratos vencendo sem renovação
- **Questionar com evidências** — assistente de IA (RAG) que responde em linguagem natural com rastreabilidade total até a fonte

**Município-piloto:** Jequié — BA (~150 mil habitantes)

## Status do Projeto

| Marco | Status |
|-------|--------|
| Validação de dados (PNCP API) | ✅ Confirmado |
| Validação de dados (Portal Transparência Local) | ✅ Ativo |
| Validação de dados (TCM-BA) | ✅ Ativo |
| Estratégia de entrada (CPSI) | 📋 Em articulação |
| Protótipo funcional | 🔧 Em desenvolvimento |

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
│  Scraping    │  Indicadores │    Claude API         │
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
| **Frontend** | React, TailwindCSS, Recharts/Apache ECharts |
| **Backend** | Python 3.12+, FastAPI, Pydantic, SQLAlchemy |
| **Banco de Dados** | PostgreSQL 16 + pgvector |
| **IA / RAG** | Claude API (Anthropic), pgvector, LangChain |
| **Ingestão** | httpx, BeautifulSoup/Scrapy, Prefect |
| **Infra** | Docker, Docker Compose |

## Estrutura do Repositório (Lente Gestor)

```
.
├── backend/
│   ├── app/
│   │   ├── api/              # Rotas da API REST
│   │   │   └── routes/
│   │   ├── connectors/       # Conectores de fontes de dados (PNCP, etc.)
│   │   ├── db/               # Configuração do banco e migrações
│   │   │   └── migrations/
│   │   ├── models/           # Modelos SQLAlchemy / Pydantic
│   │   ├── services/         # Lógica de negócio e cruzamentos
│   │   ├── config.py         # Configurações da aplicação
│   │   └── main.py           # Entrypoint FastAPI
│   ├── tests/                # Testes automatizados
│   ├── pyproject.toml        # Dependências Python
│   └── requirements.txt      # Lock de dependências
├── frontend/                 # Aplicação React (a ser inicializado)
├── scripts/                  # Scripts utilitários
├── data/                     # Dados locais (não versionado)
├── docs/                     # Documentação técnica
│   ├── ARCHITECTURE.md       # Arquitetura detalhada
│   └── DATA_SOURCES.md       # Mapa de fontes de dados
├── .env.example              # Template de variáveis de ambiente
├── .gitignore
├── docker-compose.yml        # PostgreSQL + pgvector
├── LICENSE
└── README.md
```

## Pré-requisitos

- Python 3.12+
- Node.js 20+ (para o frontend)
- Docker e Docker Compose
- Chave de API da Anthropic (para a camada RAG)

## Quickstart

```bash
# 1. Clone o repositório
git clone <repo-url>
cd <repo-name>

# 2. Copie e configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações

# 3. Suba o PostgreSQL com pgvector
docker compose up -d

# 4. Configure o backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 5. Execute as migrações
alembic upgrade head

# 6. Inicie o servidor de desenvolvimento
uvicorn app.main:app --reload

# 7. (Em outro terminal) Configure o frontend
cd frontend
npm install
npm run dev
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
