# Mapa de Fontes de Dados

## 1. PNCP — Portal Nacional de Contratações Públicas

### Informações Gerais

| Campo | Valor |
|-------|-------|
| **URL Base API** | `https://pncp.gov.br/api/consulta/v1/` |
| **Documentação** | [Swagger PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html) |
| **Autenticação** | Nenhuma (API pública) |
| **Formato** | JSON |
| **CNPJ Jequié** | `13894878000160` |
| **ID Esfera** | Municipal |

### Endpoints Relevantes

#### Contratações
```
GET /contratacoes/publicacao
Parâmetros:
  - dataInicial (YYYYMMDD)
  - dataFinal (YYYYMMDD)
  - cnpjOrgao
  - codigoModalidadeContratacao
  - pagina
  - tamanhoPagina (max: 500)
```

#### Contratos
```
GET /contratos/publicacao
Parâmetros:
  - dataInicial (YYYYMMDD)
  - dataFinal (YYYYMMDD)
  - cnpjOrgao
  - pagina
  - tamanhoPagina
```

#### PCA (Plano de Contratações Anual)
```
GET /pca/v2/itens
Parâmetros:
  - cnpjOrgao
  - anoExercicio (2024, 2025, 2026)
  - pagina
  - tamanhoPagina
```

#### Atas de Registro de Preço
```
GET /atas
Parâmetros:
  - cnpjOrgao
  - dataInicial
  - dataFinal
```

### Dados Validados para Jequié

| Tipo | Volume Identificado | Período |
|------|-------------------|---------|
| Contratações (compras) | 117+ registros | 2024 |
| Editais | 97+ | 2025 |
| Contratações diretas | 20+ | 2025 |
| PCA publicado | Sim | 2024, 2025, 2026 |

### Limitações Conhecidas

Documentadas pela Transparência Brasil (2024):

1. **Paginação limitada** — Não há garantia de completude em consultas com muitos resultados
2. **Campos nulos** — Alguns campos opcionais frequentemente não são preenchidos
3. **Fragmentação** — Dados de uma mesma contratação podem estar dispersos em múltiplos endpoints
4. **Rastreamento por item** — Não é possível acompanhar contratos por item individual
5. **Inconsistências temporais** — Datas de publicação nem sempre refletem a cronologia real

### Estratégia de Contorno

- Consultas com janelas temporais sobrepostas para garantir completude
- Validação cruzada entre endpoints (contratação ↔ contrato ↔ ata)
- Log de campos nulos para análise de qualidade
- Deduplicação por identificador único (sequencial + ano + CNPJ)

---

## 2. Portal de Transparência Local

### Informações Gerais

| Campo | Valor |
|-------|-------|
| **URL Principal** | `https://jequie.ba.gov.br/transparencia` |
| **URL Portal Dedicado** | `https://transparencia.jequie.ba.gov.br` |
| **Método de Acesso** | Scraping estruturado ou acesso direto |

### Dados Disponíveis

| Categoria | Dados | Prioridade para MVP |
|-----------|-------|---------------------|
| Licitações | Editais, resultados, atas | Alta |
| Contratos | Vigência, valores, fiscais | Alta |
| Despesas | Empenhos, liquidações, pagamentos | Alta |
| Receitas | Arrecadação por fonte | Média |
| Folha de pagamento | Servidores, cargos, remuneração | Média |
| Terceirizados | Contratos, postos, valores | Média |
| Dívida ativa | Valores, situação | Baixa |
| Diário Oficial | Publicações oficiais | Baixa |
| Dados de saúde | Indicadores, estabelecimentos | Futura |
| PCA local | Plano de contratações | Alta |

### Cruzamentos Possíveis

- **Folha × Fiscais de contrato** — Verificar se fiscais designados estão ativos na folha
- **Despesas × Contratos** — Correlacionar empenhos com contratos originais
- **Receitas × Execução orçamentária** — Verificar equilíbrio fiscal por período

### Observações

O acesso direto ao sistema de gestão da prefeitura (via parceria institucional) eliminaria a necessidade de scraping e forneceria dados mais completos e estruturados. O colaborador com acesso à gestão municipal é essencial para viabilizar essa integração.

---

## 3. TCM-BA — Tribunal de Contas dos Municípios da Bahia

### Informações Gerais

| Campo | Valor |
|-------|-------|
| **Inspetoria** | 6ª Inspetoria Regional de Controle Externo |
| **URL** | `https://www.tcm.ba.gov.br` |
| **Método de Acesso** | Portal público (a investigar APIs) |

### Sistemas Disponíveis

| Sistema | Sigla | Dados | Uso na Plataforma |
|---------|-------|-------|-------------------|
| Cadastro de Obras | SICOB | Obras e serviços de engenharia | Cruzar com licitações de obras no PNCP |
| Publicidade | SIP | Gastos com publicidade institucional | Verificar limites legais |
| Pessoal | SAPPE | Acompanhamento de pagamento de pessoal | Cruzar com folha local |
| Educação/Saúde | SIES | Gastos em educação e saúde | Verificar mínimos constitucionais |

### Valor para Cruzamento

Os dados do TCM-BA permitem comparar o que foi **licitado/contratado** (PNCP) com o que foi **reportado ao tribunal** (TCM-BA), identificando discrepâncias entre execução real e prestação de contas.

---

## 4. Fontes Futuras (Pós-MVP)

### Portal da Transparência Federal
- **URL API**: `https://api.portaldatransparencia.gov.br/`
- **Dados**: Transferências da União para Jequié (convênios, FPM, SUS, FUNDEB)
- **Uso**: Cruzar transferências recebidas com execução local

### SICONFI / STN
- **URL**: `https://siconfi.tesouro.gov.br/`
- **Dados**: Balanços contábeis consolidados (RREO, RGF)
- **Uso**: Indicadores fiscais e compliance LRF

### Diário Oficial do Município
- **Dados**: Nomeações, exonerações, portarias, decretos
- **Uso**: Correlacionar atos administrativos com movimentações contratuais
