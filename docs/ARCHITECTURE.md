# Arquitetura Técnica

## Visão Geral

A plataforma é composta por quatro camadas principais, cada uma com responsabilidades bem definidas. A arquitetura prioriza modularidade e simplicidade — evitando complexidade prematura enquanto mantém o caminho aberto para escala.

```
                          ┌──────────────┐
                          │   Usuário     │
                          │   (Gestor)    │
                          └──────┬───────┘
                                 │
                    ┌────────────▼────────────┐
                    │     FRONTEND (React)     │
                    │  ┌─────────┐ ┌────────┐ │
                    │  │Dashboards│ │Chat IA │ │
                    │  └─────────┘ └────────┘ │
                    │  ┌─────────┐ ┌────────┐ │
                    │  │ Alertas │ │Relatórios│ │
                    │  └─────────┘ └────────┘ │
                    └────────────┬────────────┘
                                 │ REST API
                    ┌────────────▼────────────┐
                    │    BACKEND (FastAPI)      │
                    │                          │
                    │  ┌──────────────────────┐│
                    │  │    API Routes         ││
                    │  │  /contratos           ││
                    │  │  /fornecedores        ││
                    │  │  /cruzamentos         ││
                    │  │  /alertas             ││
                    │  │  /chat                ││
                    │  └──────────────────────┘│
                    │                          │
                    │  ┌──────────────────────┐│
                    │  │    Services           ││
                    │  │  Cruzamentos          ││
                    │  │  Indicadores          ││
                    │  │  Alertas              ││
                    │  │  RAG Pipeline         ││
                    │  └──────────────────────┘│
                    │                          │
                    │  ┌──────────────────────┐│
                    │  │    Connectors         ││
                    │  │  PNCP API             ││
                    │  │  Portal Transparência ││
                    │  │  TCM-BA               ││
                    │  └──────────────────────┘│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  PostgreSQL + pgvector    │
                    │                          │
                    │  Dados normalizados       │
                    │  Views materializadas     │
                    │  Embeddings (RAG)         │
                    └──────────────────────────┘
```

## Camada 1 — Ingestão de Dados

### Responsabilidade
Consumir, validar e persistir dados das fontes externas.

### Conectores

**PNCP (prioridade máxima)**
- API REST pública, sem autenticação
- Base URL: `https://pncp.gov.br/api/consulta/v1/`
- Endpoints principais:
  - `/contratacoes/publicacao` — Contratações por período e órgão
  - `/contratos/publicacao` — Contratos por período
  - `/pca/v2/itens` — Itens do Plano de Contratações Anual
  - `/atas` — Atas de registro de preço
- CNPJ Jequié: `13894878000160`
- Limitações conhecidas: paginação limitada, campos nulos, fragmentação entre endpoints

**Portal de Transparência Local**
- URLs: `jequie.ba.gov.br/transparencia`, `transparencia.jequie.ba.gov.br`
- Método: Scraping estruturado (BeautifulSoup/Scrapy) ou acesso direto ao sistema
- Dados-alvo: despesas, receitas, folha de pagamento, terceirizados

**TCM-BA**
- Sistemas: SICOB (obras), SIP (publicidade), SAPPE (pessoal), SIES (educação/saúde)
- Método: a definir (portal público + possível API)

### Pipeline de Ingestão

```
Fonte Externa ──► Connector ──► Validação ──► Normalização ──► PostgreSQL
                                  │
                                  └──► Log de erros / dados rejeitados
```

Orquestração via **Prefect** (ou cron jobs simples no MVP).

### Frequência de Atualização

| Fonte | Frequência Alvo |
|-------|----------------|
| PNCP | Diária |
| Portal Transparência | Semanal |
| TCM-BA | Sob demanda |

## Camada 2 — Analítica e Cruzamentos

### Responsabilidade
Transformar dados brutos em informação acionável.

### Cruzamentos Prioritários

1. **PCA vs. Execução** — O que foi planejado no Plano de Contratações Anual está sendo executado? Quais itens estão atrasados ou com desvio significativo?

2. **Concentração de Fornecedores** — Quais fornecedores concentram um percentual desproporcional dos contratos? Há padrão de direcionamento?

3. **Contratos Críticos** — Quais contratos vencem nos próximos 30/60/90 dias sem processo de renovação? Quais estão com aditivos acumulados acima de 25%?

4. **Desvio Orçamentário por Secretaria** — Qual secretaria está mais acima/abaixo do orçamento previsto? Em quais categorias de despesa?

### Indicadores

| Indicador | Fórmula | Alerta |
|-----------|---------|--------|
| Índice de concentração (HHI) | Σ(participação²) por fornecedor | HHI > 0.25 |
| Desvio PCA | (Executado - Planejado) / Planejado | > ±30% |
| Velocidade contratual | Dias entre publicação e assinatura | > 90 dias |
| Taxa de aditivos | Valor aditivos / Valor original | > 25% |

### Implementação

- **Views materializadas** no PostgreSQL para cálculos recorrentes
- **Refresh** periódico (diário ou sob demanda)
- **dbt** como camada de transformação quando a complexidade justificar

## Camada 3 — Apresentação (Frontend)

### Responsabilidade
Interface web responsiva para gestores municipais.

### Princípios de Design
- Cada tela responde uma **pergunta específica** do gestor
- Priorizar **ação** sobre informação — "o que preciso fazer?" acima de "o que aconteceu?"
- Alertas com **severidade** visual clara
- Mobile-friendly (gestores acessam de qualquer lugar)

### Telas Prioritárias (MVP)

1. **Visão Geral** — Resumo executivo: contratos ativos, alertas pendentes, indicadores-chave
2. **Contratos** — Lista filtrada com status, valores, vencimentos, fornecedor
3. **Fornecedores** — Ranking por valor, concentração, histórico
4. **PCA vs. Execução** — Comparativo visual com desvios destacados
5. **Alertas** — Lista priorizada de inconsistências detectadas
6. **Chat IA** — Interface de pergunta em linguagem natural

### Stack
- **React** com TypeScript
- **TailwindCSS** para estilização
- **Recharts** ou **Apache ECharts** para visualizações
- **React Query** para gerenciamento de estado do servidor

## Camada 4 — IA / RAG

### Responsabilidade
Permitir consultas em linguagem natural com respostas rastreáveis.

### Pipeline RAG

```
Pergunta do Gestor
        │
        ▼
┌───────────────┐
│  Embedding da │
│   pergunta    │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Busca vetorial│ ◄── pgvector (PostgreSQL)
│  (top-k docs) │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Construção   │
│  do contexto  │
│  (dados +     │
│   metadados)  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ Gemini 3.1 Pro│ ◄── Prompt com contexto + instrução de rastreabilidade
│  (Vertex AI)  │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  Resposta com │
│  citações de  │
│  fonte        │
└───────────────┘
```

### Princípio Inegociável
> Toda resposta da IA deve ser rastreável até o dado-fonte. Em contexto de governança pública, uma resposta sem fonte é pior que nenhuma resposta.

### Estratégia de Indexação
- Dados estruturados (contratos, contratações, PCA) são convertidos em documentos textuais com metadados
- Cada documento inclui: fonte original, data de atualização, entidade responsável
- Embeddings gerados via **Gemini Embedding 2** (`gemini-embedding-2-preview`) — até 3072 dimensões, multimodal (texto, imagens, vídeo, áudio, PDF), 100+ idiomas
- Armazenamento em pgvector (extensão do PostgreSQL — sem infraestrutura adicional)
- Task instructions inline no prompt: `task: search result | query: {pergunta}` para buscas, `title: {titulo} | text: {conteudo}` para documentos

### Modelo de Linguagem
- **Gemini 3.1 Pro** (Google, via Vertex AI) — 1M tokens de contexto, forte em português, 2.5× melhor raciocínio que Gemini 3 Pro
- Model ID: `gemini-3.1-pro-preview`
- System prompt inclui: regras de rastreabilidade, formato de citação, comportamento "não sei" quando dados insuficientes
- Autenticação via Application Default Credentials (ADC) — sem API key explícita

## Decisões Técnicas

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| Banco de dados | PostgreSQL + pgvector | Banco único para dados + embeddings; reduz complexidade operacional |
| ORM | SQLAlchemy 2.0 | Maturidade, tipagem, suporte a async |
| Migrações | Alembic | Padrão com SQLAlchemy |
| API Framework | FastAPI | Performance, tipagem automática, docs OpenAPI |
| Frontend | React + TypeScript | Ecossistema maduro, componentes reutilizáveis |
| Orquestração | Prefect (futuro) / cron (MVP) | Simplicidade no MVP, migração fácil |
|| LLM | Gemini 3.1 Pro (Vertex AI) | 1M contexto, forte em PT-BR, coberto por créditos GCP |

## Segurança

- Dados consumidos são **públicos por lei** (Lei 14.133/2021 + Lei 12.527/2011)
- Autenticação de usuários via JWT
- HTTPS obrigatório em produção
- Variáveis sensíveis (API keys) em `.env`, nunca no código
- LGPD: não há dados pessoais sensíveis nas fontes primárias (licitações são públicas)
