# Extensão: Camada Orçamentária (SICONFI + IBGE)

> **Status:** Proposta — a implementar
> **Escopo:** Integrar dados de execução orçamentária, indicadores fiscais e contextuais municipais às fontes já ingeridas (PNCP).
> **Motivação:** Hoje a Lente enxerga o que foi *contratado*; com esta extensão passa a enxergar também o que foi *orçado e executado*, habilitando cruzamentos que nenhuma das fontes viabiliza sozinha.

---

## 1. Objetivo

Adicionar duas novas fontes de dados federais à plataforma:

1. **SICONFI** — Sistema de Informações Contábeis e Fiscais do Setor Público Brasileiro (Tesouro Nacional). Fornece relatórios padronizados de receita, despesa e indicadores fiscais de todos os municípios brasileiros.
2. **IBGE** — Dados contextuais do município (população, PIB, indicadores socioeconômicos) usados para normalização e cálculo de indicadores per capita.

Com essas fontes ingeridas, o gestor passa a responder perguntas como:

- "A Secretaria de Saúde executou quanto do orçamento previsto neste bimestre?"
- "Jequié está dentro dos limites da LRF para despesa com pessoal?"
- "Qual o gasto per capita em educação comparado a municípios de porte similar?"
- "Os contratos firmados em uma função específica batem com o empenhado no RREO?"

Todas as respostas com rastreabilidade até a fonte (RAG), no mesmo padrão dos dados PNCP.

---

## 2. Fontes de Dados

### 2.1 SICONFI — API REST pública

**Base URL:** `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`
**Autenticação:** Nenhuma
**Formato:** JSON
**Paginação:** 5.000 itens por página (padrão)
**Documentação:** `https://apidatalake.tesouro.gov.br/docs/siconfi/`

**Identificador de Jequié:**
- `id_ente` (código IBGE): `2918001`
- `cod_ibge` também aceito em alguns endpoints

**Endpoints relevantes:**

| Relatório | Endpoint | Periodicidade | Principais dados |
|-----------|----------|---------------|------------------|
| RREO | `/rreo` | Bimestral | Receitas realizadas vs. previstas, despesas por função/subfunção |
| RGF | `/rgf` | Quadrimestral | Despesa com pessoal, dívida, garantias, limites LRF |
| DCA | `/dca` | Anual | Balanço patrimonial, demonstrações contábeis completas |
| MSC | `/msc` | Mensal | Matriz de Saldos Contábeis (granular, uso avançado) |
| Entes | `/entes` | — | Metadados e identificadores dos entes federativos |

**Parâmetros comuns:**
- `an_exercicio` — ano de referência
- `nr_periodo` — bimestre (1-6) para RREO, quadrimestre (1-3) para RGF
- `id_ente` — código IBGE do município
- `no_anexo` — nome do anexo específico do relatório

**Exemplo de chamada (RREO bimestre 6 de 2024):**

```
GET https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo
  ?an_exercicio=2024
  &nr_periodo=6
  &co_tipo_demonstrativo=RREO
  &id_ente=2918001
```

### 2.2 IBGE — APIs de Serviço

**Base URL:** `https://servicodados.ibge.gov.br/api/`
**Autenticação:** Nenhuma
**Formato:** JSON

**Endpoints relevantes:**

| Dado | Endpoint | Uso |
|------|----------|-----|
| Localidades | `/v1/localidades/municipios/2918001` | Metadados do município |
| População (estimativa) | `/v3/agregados/6579/periodos/-6/variaveis/9324?localidades=N6[2918001]` | Série histórica de população |
| PIB municipal | `/v3/agregados/5938/periodos/-10/variaveis/37?localidades=N6[2918001]` | PIB a preços correntes |
| Censo 2022 | `/v3/agregados/9514/...` | Dados demográficos detalhados |

**Notas sobre a API v3 (SIDRA):**
- O parâmetro `periodos=-N` retorna os últimos N períodos disponíveis
- `localidades=N6[código]` filtra por município (N6 = nível municipal)
- Retorno em estrutura aninhada; parser precisa de cuidado

### 2.3 Relação com fontes já existentes

| Fonte | Tipo | Já ingerida? |
|-------|------|--------------|
| PNCP | Contratações, contratos, PCA | ✅ |
| SICONFI | Execução orçamentária, indicadores fiscais | 🔧 Esta extensão |
| IBGE | Dados contextuais | 🔧 Esta extensão |
| Portal Transparência Jequié | Empenhos, despesas detalhadas, folha | 📋 Próxima fase |
| TCM-BA | SICOB, SIP, SAPPE, SIES | 📋 Próxima fase |

Crucialmente, **SICONFI e Portal de Transparência Local são complementares**, não redundantes. O SICONFI traz dados consolidados e padronizados nacionalmente, enquanto o portal local tem granularidade por empenho individual. Ingerir o SICONFI primeiro é estrategicamente mais fácil (API pública, dados padronizados) e cobre a maior parte dos cruzamentos de alto valor.

---

## 3. Modelagem de Dados

Três novas tabelas, todas seguindo as convenções já estabelecidas em `backend/app/models/contratacoes.py` (UUID como PK, timestamps automáticos, campo `fonte` para rastreabilidade, `dados_brutos` para auditoria).

### 3.1 `execucao_orcamentaria`

Registra cada célula dos relatórios RREO/DCA do SICONFI em formato longo — uma linha por combinação (anexo, coluna, conta). Esta modelagem espelha 1:1 a resposta da API do Tesouro (ORDS), preservando rastreabilidade perfeita à fonte oficial conforme a ADR 10.2.

**Por que formato longo (e não pivot):** a API SICONFI retorna sempre o mesmo shape — 15 campos fixos, independentemente do anexo solicitado. Função, subfunção, natureza, categoria etc. — quando existem — ficam codificadas em `anexo` + `rotulo` + `coluna` + `cod_conta` + `conta`. Pivotar isso para colunas explícitas (como `valor_previsto`, `valor_empenhado` etc.) exigiria lógica per-anexo frágil e perderia informação dos anexos que não se encaixam nesse molde. Agregações por função/natureza são suportadas via `WHERE` e `GROUP BY` nas rotas da API (Fase 4) sem perder granularidade.

**Mapeamento direto da resposta da API:**

| Campo do modelo | Origem no item da API | Exemplo |
|-----------------|----------------------|---------|
| `exercicio` | `exercicio` | 2024 |
| `periodo` | `periodo` | 6 (bimestre) |
| `periodicidade` | `periodicidade` | `B` (bimestral) |
| `tipo_relatorio` | `demonstrativo` | `RREO` |
| `anexo` | `anexo` | `RREO-Anexo 02` |
| `rotulo` | `rotulo` | `Total das Despesas Exceto Intra-Orçamentárias` |
| `coluna` | `coluna` | `DESPESAS EMPENHADAS` |
| `cod_conta` | `cod_conta` | `RREO2TotalDespesas` |
| `conta` | `conta` | `Saúde` |
| `valor` | `valor` | `11720606.30` |
| `cod_ibge` | `cod_ibge` | `2918001` |

```python
class ExecucaoOrcamentaria(Base):
    """
    Uma célula do relatório RREO/DCA do SICONFI.

    Formato longo: um registro representa (anexo × coluna × conta)
    em um (exercício, período) de um ente federativo.
    """

    __tablename__ = "execucao_orcamentaria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Período / tipo de relatório
    exercicio: Mapped[int] = mapped_column(Integer, index=True)
    periodo: Mapped[int | None] = mapped_column(Integer, index=True)  # bimestre 1-6; NULL em DCA
    periodicidade: Mapped[str | None] = mapped_column(String(5))  # B, Q, A
    tipo_relatorio: Mapped[str] = mapped_column(String(10), index=True)  # RREO, DCA

    # Classificação SICONFI (long format)
    anexo: Mapped[str] = mapped_column(String(100), index=True)
    rotulo: Mapped[str | None] = mapped_column(String(255))
    coluna: Mapped[str] = mapped_column(String(255), index=True)
    cod_conta: Mapped[str] = mapped_column(String(255), index=True)
    # conta é discriminador (várias funções/linhas por cod_conta)
    conta: Mapped[str] = mapped_column(String(500))

    # Valor da célula
    valor: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Órgão + código IBGE
    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    orgao: Mapped["Orgao"] = relationship()
    cod_ibge: Mapped[str] = mapped_column(String(7), index=True)

    # Rastreabilidade
    fonte: Mapped[str] = mapped_column(String(20))  # SICONFI_RREO, SICONFI_DCA
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_exec_orc_unique",
            "orgao_id", "exercicio", "periodo", "tipo_relatorio",
            "anexo", "cod_conta", "coluna", "conta",
            unique=True,
        ),
        Index("ix_exec_orc_exerc_anexo", "exercicio", "anexo"),
    )
```

### 3.2 `indicadores_fiscais`

Armazena indicadores calculados a partir do RGF — principalmente os limites da LRF e mínimos constitucionais. Visão por quadrimestre, com referência ao limite legal para facilitar alertas.

```python
class IndicadorFiscal(Base):
    """
    Indicadores fiscais do município (LRF, mínimos constitucionais).

    Fonte principal: SICONFI — RGF (quadrimestral).
    Cada registro representa um indicador em um período específico.
    """

    __tablename__ = "indicadores_fiscais"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Período
    exercicio: Mapped[int] = mapped_column(Integer, index=True)
    quadrimestre: Mapped[int | None] = mapped_column(Integer)  # 1, 2 ou 3

    # Indicador
    codigo: Mapped[str] = mapped_column(String(50), index=True)
    # ex: DESPESA_PESSOAL_PCT_RCL, DIVIDA_CONSOLIDADA_PCT_RCL,
    #     APLIC_MIN_SAUDE_PCT, APLIC_MIN_EDUCACAO_PCT
    descricao: Mapped[str] = mapped_column(String(255))

    # Valores
    valor: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    limite_legal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unidade: Mapped[str] = mapped_column(String(20))  # PERCENTUAL, MONETARIO

    # Status derivado (calculado na ingestão)
    situacao: Mapped[str | None] = mapped_column(String(30))
    # OK, ALERTA (> 90% do limite), EXCEDIDO, ABAIXO_MINIMO

    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    orgao: Mapped["Orgao"] = relationship()

    fonte: Mapped[str] = mapped_column(String(20))  # SICONFI_RGF
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_indic_fisc_unique",
            "orgao_id", "exercicio", "quadrimestre", "codigo",
            unique=True,
        ),
    )
```

### 3.3 `dados_municipio`

Contexto socioeconômico do município — uma linha por exercício. Tabela pequena, mas essencial para indicadores per capita e comparações entre municípios.

```python
class DadosMunicipio(Base):
    """
    Dados contextuais do município em um dado exercício.

    Fonte principal: IBGE (população, PIB). Demais campos podem vir de
    outras fontes ao longo do tempo.
    """

    __tablename__ = "dados_municipio"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    orgao: Mapped["Orgao"] = relationship()
    codigo_ibge: Mapped[str] = mapped_column(String(7), index=True)

    exercicio: Mapped[int] = mapped_column(Integer, index=True)

    # Dados do IBGE
    populacao: Mapped[int | None] = mapped_column(Integer)
    pib_corrente: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    pib_per_capita: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Dados fiscais calculados (podem ser derivados do SICONFI)
    rcl_estimada: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    fonte: Mapped[str] = mapped_column(String(20))  # IBGE, CALCULADO
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_dados_mun_unique", "orgao_id", "exercicio", unique=True),
    )
```

---

## 4. Conectores

Dois novos arquivos em `backend/app/connectors/`, seguindo o padrão assíncrono de `pncp.py` (httpx + tenacity + structlog).

### 4.1 `siconfi.py`

```python
"""Cliente assíncrono para a API do SICONFI (Tesouro Nacional)."""

from typing import Any
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()
BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"


class SICONFIClient:
    """Cliente para os endpoints do SICONFI."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> "SICONFIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _get(self, path: str, params: dict) -> dict:
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def rreo(
        self,
        *,
        an_exercicio: int,
        nr_periodo: int,
        id_ente: str,
        no_anexo: str | None = None,
    ) -> dict:
        """Consulta o Relatório Resumido da Execução Orçamentária."""
        params = {
            "an_exercicio": an_exercicio,
            "nr_periodo": nr_periodo,
            "co_tipo_demonstrativo": "RREO",
            "id_ente": id_ente,
        }
        if no_anexo:
            params["no_anexo"] = no_anexo
        return await self._get("/rreo", params)

    async def rgf(
        self,
        *,
        an_exercicio: int,
        nr_periodo: int,
        id_ente: str,
        co_poder: str = "E",  # E=Executivo, L=Legislativo
    ) -> dict:
        """Consulta o Relatório de Gestão Fiscal."""
        params = {
            "an_exercicio": an_exercicio,
            "nr_periodo": nr_periodo,
            "co_tipo_demonstrativo": "RGF",
            "id_ente": id_ente,
            "co_poder": co_poder,
        }
        return await self._get("/rgf", params)

    async def dca(
        self,
        *,
        an_exercicio: int,
        id_ente: str,
        no_anexo: str | None = None,
    ) -> dict:
        """Consulta a Declaração de Contas Anuais."""
        params = {"an_exercicio": an_exercicio, "id_ente": id_ente}
        if no_anexo:
            params["no_anexo"] = no_anexo
        return await self._get("/dca", params)
```

### 4.2 `ibge.py`

```python
"""Cliente assíncrono para APIs de serviço do IBGE."""

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()
BASE_URL = "https://servicodados.ibge.gov.br/api"


class IBGEClient:
    """Cliente para endpoints de localidades e SIDRA (agregados)."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)

    async def __aenter__(self) -> "IBGEClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _get(self, path: str) -> dict | list:
        resp = await self._client.get(path)
        resp.raise_for_status()
        return resp.json()

    async def municipio(self, codigo_ibge: str) -> dict:
        """Metadados do município."""
        return await self._get(f"/v1/localidades/municipios/{codigo_ibge}")

    async def populacao(self, codigo_ibge: str, ultimos_periodos: int = 6) -> list:
        """Série histórica de população estimada (tabela SIDRA 6579)."""
        path = (
            f"/v3/agregados/6579/periodos/-{ultimos_periodos}"
            f"/variaveis/9324?localidades=N6[{codigo_ibge}]"
        )
        return await self._get(path)

    async def pib(self, codigo_ibge: str, ultimos_periodos: int = 10) -> list:
        """PIB a preços correntes (tabela SIDRA 5938)."""
        path = (
            f"/v3/agregados/5938/periodos/-{ultimos_periodos}"
            f"/variaveis/37?localidades=N6[{codigo_ibge}]"
        )
        return await self._get(path)
```

---

## 5. Serviços de Ingestão

Dois novos services em `backend/app/services/` — o padrão é o mesmo do `ingestao_pncp.py`: função `async` que recebe o conector, normaliza cada registro, e faz upsert transacional.

### 5.1 `ingestao_orcamento.py`

Responsabilidade: ingerir RREO, RGF e DCA para um município num dado exercício.

**Fluxo:**
1. Para cada bimestre (1-6), consultar RREO do SICONFI.
2. Para cada quadrimestre (1-3), consultar RGF.
3. Consultar DCA do exercício (visão anual consolidada).
4. Para cada item, normalizar e fazer upsert em `execucao_orcamentaria` ou `indicadores_fiscais` conforme o tipo.
5. Calcular situação (OK / ALERTA / EXCEDIDO) comparando com limites legais.
6. Logar métricas (total ingerido, erros, duração).

**Limites LRF a calcular a partir do RGF (executivo municipal):**

| Código | Descrição | Limite legal |
|--------|-----------|--------------|
| `DESPESA_PESSOAL_PCT_RCL` | Despesa total com pessoal | 54% RCL |
| `DESPESA_PESSOAL_PRUDENCIAL` | Limite prudencial (alerta) | 51,3% RCL |
| `DIVIDA_CONSOLIDADA_PCT_RCL` | Dívida consolidada líquida | 120% RCL |
| `OP_CREDITO_PCT_RCL` | Operações de crédito | 16% RCL |
| `GARANTIAS_PCT_RCL` | Garantias concedidas | 22% RCL |
| `APLIC_MIN_SAUDE_PCT` | Aplicação em saúde (CF Art. 198 §2º) | Mín. 15% |
| `APLIC_MIN_EDUCACAO_PCT` | Aplicação em educação (CF Art. 212) | Mín. 25% |

Situação derivada:
- `OK` — dentro dos limites
- `ALERTA` — entre 90% e 100% do limite máximo
- `EXCEDIDO` — acima do limite
- `ABAIXO_MINIMO` — abaixo do mínimo constitucional (para saúde/educação)

### 5.2 `ingestao_ibge.py`

Mais simples: uma chamada de metadados + uma de população + uma de PIB por exercício, upsert na tabela `dados_municipio`.

### 5.3 Scripts CLI

Seguindo o padrão de `scripts/ingest_pncp.py`:

```bash
# Ingerir execução orçamentária (SICONFI) para um exercício
PYTHONPATH=. python -m scripts.ingest_orcamento --exercicio 2024

# Ingerir dados contextuais do IBGE
PYTHONPATH=. python -m scripts.ingest_ibge --codigo-ibge 2918001

# Via Makefile
make ingest-orcamento
make ingest-ibge
```

---

## 6. Rotas API

Novo arquivo `backend/app/api/routes/orcamento.py`:

```python
# Listar execução orçamentária com filtros
GET /api/orcamento/execucao
  ?exercicio=2024&funcao=Saude&tipo=DESPESA

# Resumo de execução por função (agregado)
GET /api/orcamento/resumo-por-funcao?exercicio=2024

# Indicadores fiscais (LRF + mínimos constitucionais)
GET /api/orcamento/indicadores?exercicio=2024&quadrimestre=3

# Dados contextuais do município
GET /api/municipio/dados?exercicio=2024

# Cruzamento: comparação PCA vs. execução
GET /api/orcamento/pca-vs-execucao?exercicio=2024
```

Schemas em `backend/app/api/schemas.py` seguindo o padrão dos existentes (`BaseModel` com `ConfigDict(from_attributes=True)`).

---

## 7. Cruzamentos e Analítica

É aqui que a extensão entrega o valor principal da Lente. Com PNCP + SICONFI na mesma base, novos serviços de cruzamento ficam possíveis em `backend/app/services/cruzamentos/`:

### 7.1 `pca_vs_execucao.py`

Compara o que a prefeitura planejou contratar (PCA do PNCP) com o que efetivamente executou por função (RREO do SICONFI). Alerta em divergências > 20%.

### 7.2 `alertas_lrf.py`

Para cada indicador de `indicadores_fiscais` em situação `ALERTA` ou `EXCEDIDO`, gera alertas proativos. Se a despesa com pessoal está próxima de 54% da RCL, cruzar com contratos de terceirização no PNCP (que poderiam ser reclassificados como substituição de mão de obra).

### 7.3 `concentracao_vs_funcao.py`

Identifica funções onde a concentração de contratos em poucos fornecedores (já calculável com dados do PNCP) coincide com alto valor executado (RREO). Um fornecedor que recebe 70% dos contratos de Saúde numa função que representa grande fatia do orçamento é um sinalizador mais forte que qualquer um dos dois isoladamente.

### 7.4 Indicadores per capita

Com `dados_municipio.populacao`, calcular automaticamente gasto per capita em Saúde, Educação, Infraestrutura, etc. Facilita benchmarking futuro com outros municípios.

---

## 8. Integração com RAG

Os dados ingeridos alimentam a camada RAG da mesma forma que os dados PNCP: documentos normalizados são convertidos em embeddings via Gemini Embedding 2 e armazenados em `pgvector`.

Novas "intenções" de pergunta passam a ser respondíveis:

| Pergunta | Fontes consultadas |
|----------|--------------------|
| "Por que Saúde está acima do orçamento?" | `execucao_orcamentaria` + `contratacoes`/`contratos` |
| "Jequié está dentro do limite da LRF?" | `indicadores_fiscais` |
| "Quais funções tiveram maior desvio entre PCA e execução?" | `itens_pca` (PNCP) + `execucao_orcamentaria` |
| "Qual o gasto per capita em educação?" | `execucao_orcamentaria` + `dados_municipio` |

A rastreabilidade (mostrar a fonte exata) continua garantida — cada resposta carrega as referências dos registros consultados, permitindo clicar e validar.

---

## 9. Faseamento

Cinco fases incrementais. Cada fase entrega valor autônomo — mesmo parando na Fase 1, o Lente já amplia significativamente sua cobertura de dados.

### Fase 1 — Execução orçamentária via RREO

**Esforço estimado:** 2-3 dias
**Entregas:**
- [ ] Conector `siconfi.py` com método `rreo()`
- [ ] Modelo `ExecucaoOrcamentaria` + migração Alembic
- [ ] Serviço `ingestao_orcamento.py` (parcial — só RREO)
- [ ] Script CLI `ingest_orcamento.py`
- [ ] Testes unitários para parsing + upsert (meta: 8+ testes)
- [ ] Ingestão real de Jequié (exercícios 2023 e 2024)

### Fase 2 — Dados contextuais IBGE

**Esforço estimado:** 1 dia
**Entregas:**
- [ ] Conector `ibge.py`
- [ ] Modelo `DadosMunicipio` + migração
- [ ] Serviço `ingestao_ibge.py` + script CLI
- [ ] Testes

### Fase 3 — Indicadores fiscais via RGF

**Esforço estimado:** 1-2 dias
**Entregas:**
- [ ] Método `rgf()` em `siconfi.py`
- [ ] Modelo `IndicadorFiscal` + migração
- [ ] Extensão do serviço para processar RGF
- [ ] Cálculo de situação (OK / ALERTA / EXCEDIDO)
- [ ] Testes cobrindo os 7 indicadores principais da LRF

### Fase 4 — API e frontend

**Esforço estimado:** 2-3 dias
**Entregas:**
- [ ] Rotas `/api/orcamento/*` e `/api/municipio/*`
- [ ] Schemas Pydantic
- [ ] Páginas no frontend: dashboard orçamentário, página de indicadores LRF
- [ ] Componentes de visualização (Recharts) — gráficos de execução por função, termômetro LRF

### Fase 5 — Cruzamentos e alertas

**Esforço estimado:** 2-3 dias
**Entregas:**
- [ ] Serviço de cruzamento `pca_vs_execucao`
- [ ] Serviço de alertas `alertas_lrf`
- [ ] Extensão do RAG para incluir documentos orçamentários
- [ ] Frontend: painel de alertas consolidado

**Esforço total estimado:** 8-12 dias de desenvolvimento focado.

---

## 10. Decisões Arquiteturais

Registro de decisões tomadas ao projetar esta extensão, no espírito de ADRs leves.

### 10.1 SICONFI antes de Portal de Transparência Local

Embora o portal local tenha granularidade maior (empenho individual), o SICONFI cobre a maior parte dos cruzamentos de alto valor e tem API padronizada e estável — sem risco de mudanças de layout que quebrariam scraping. O portal local entra numa fase posterior para enriquecer o que o SICONFI já fornece.

### 10.2 Armazenamento desnormalizado por período

`execucao_orcamentaria` duplica dados em algum grau (valores do bimestre 6 contêm valores acumulados dos bimestres anteriores). Optamos por manter a estrutura do SICONFI em vez de normalizar agressivamente — isso simplifica a ingestão e preserva rastreabilidade perfeita com a fonte oficial.

### 10.3 Cálculo de situação na ingestão, não na consulta

Situações como `ALERTA` / `EXCEDIDO` são calculadas e persistidas na ingestão, não derivadas em tempo de consulta. Isso permite indexação, queries simples, e histórico de quando um indicador mudou de situação. O custo é re-ingerir quando mudam os limites legais — aceitável dado que esses limites são estáveis.

### 10.4 `dados_municipio` como tabela separada, não colunas em `orgaos`

Dados contextuais mudam anualmente (população, PIB). Mantê-los em `orgaos` forçaria um design temporal estranho. Tabela separada com uma linha por exercício é mais limpa.

### 10.5 Sem cache de respostas da API

Os endpoints do SICONFI e IBGE são lentos para dados grandes mas chamados infrequentemente (ingestão batch). Adicionar cache Redis agora é complexidade prematura. Se necessário mais tarde, o padrão de retry do tenacity já mitiga falhas transientes.

---

## 11. Referências

- **SICONFI API** — https://apidatalake.tesouro.gov.br/docs/siconfi/
- **SICONFI (portal)** — https://siconfi.tesouro.gov.br/
- **IBGE Serviço de Dados** — https://servicodados.ibge.gov.br/api/docs/
- **LC 101/2000 (LRF)** — limites de despesa com pessoal (Art. 19-20), dívida consolidada (Art. 30-31)
- **CF/88 Art. 198 §2º** — mínimo de 15% em saúde
- **CF/88 Art. 212** — mínimo de 25% em educação
- **EC 132/2023** — ajustes recentes a regras fiscais municipais

---

## 12. Próximos Passos

1. Revisar este documento com o grupo de cofundadores
2. Criar issues no repositório, uma por item de checklist da Fase 1
3. Abrir branch `feat/conector-siconfi` e começar pela Fase 1
4. Após Fase 1 concluída e validada com dados reais de Jequié, seguir com Fase 2

---

*Última atualização: 2026-04-16*
