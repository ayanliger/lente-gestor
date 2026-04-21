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

### Diário Oficial do Município
- **Dados**: Nomeações, exonerações, portarias, decretos
- **Uso**: Correlacionar atos administrativos com movimentações contratuais

---

## 5. Município Online (Portal da Transparência)

**Fornecedor**: terceiro (distinto do ERP municipal, que é E&L GPI).
**Escopo coberto pela Lente**: arrecadação tributária mensal, com drill-down por recolhimento individual (banco recebedor + data).

### URL base
- `https://municipioonline.com.br/<slug>/cidadao/receita`
- Slug de Jequié: `ba/prefeitura/jequie`

### Protocolo
Portal é **ASP.NET Web Forms + AngularJS**. Não há API REST formal. Ingestão replica o fluxo do navegador:

1. **GET** da página → extrair `__VIEWSTATE`, `__EVENTVALIDATION`, `__VIEWSTATEGENERATOR`.
2. **POST form-urlencoded** na mesma URL com `__EVENTTARGET=ctl00$body$btnFiltrarRS`, `ctl00$body$hfAnoR`, `ctl00$body$hfMesR` → HTML com linhas por item de receita (cada `<tr data-key>`).
3. **POST JSON** em `?o=R` com `{NuCnpj, DtAno, DtAnoMes, DtPeriodo, FlCovid19, CdItemReceita}` → drill-down com recolhimentos individuais (classes CSS `.dt_emissao`, `.nu_processo`, `.ds_contaBanco`, `.vl_realizado`, `.ds_observacao`).

### Campos capturados

**Agregado** (`arrecadacao`): código de receita do Tesouro (10+ dígitos), descrição, poder, categoria (Obrigatória/Voluntária), fonte de recursos, valores previsto/atualizado/período/acumulado, data de emissão.

**Detalhe** (`recolhimento_detalhe`): data de emissão, número de processo, banco recebedor, valor do recolhimento, histórico.

### Classificação de espécie
Derivada do prefixo do código do STN: `111*` Impostos, `112*` Taxas, `113*` Contribuição de Melhoria, `12*` Contribuições, `13*`–`19*` Patrimonial/Serviços/Transferências/Não Tributária, `2*` Capital, `7*`/`8*` Intraorçamentária.

### Limitações
- **Contribuinte individual** (nome/CPF do pagador) não é exposto no portal público — inviável capturar sem contrato direto com o ERP.
- Protocolo ASP.NET é frágil a mudanças de layout do portal; logging estruturado no conector facilita diagnóstico.

### Cobertura atual
- Agregado mensal (`arrecadacao`) disponível para **2023–2026**. Backfill executado via `make ingest-arrecadacao-historico`; ingestão incremental mensal via `make ingest-arrecadacao ano=AAAA`.
- Drill-down por recolhimento (`recolhimento_detalhe`) permanece **opt-in** (`--com-detalhes`) porque gera centenas de requests extras por mês. Visualização por banco no frontend está oculta até o drill-down ser ingerido rotineiramente.

### Lacuna conhecida: exercícios 2020–2022

O portal responde aos filtros `hfAnoR=2020..2022` devolvendo apenas as **linhas de previsão orçamentária** (uma entrada por item × fonte de recursos) com:

- `data_emissao = 01/01/AAAA` (sentinela — 1º de janeiro do ano);
- `valor_previsto`/`valor_atualizado` preenchidos;
- `valor_arrecadado_periodo = R$ 0,00` e `valor_arrecadado_acumulado = R$ 0,00` em 100% das linhas.

Comparativo validado em 04/2026 para o mês 6 de cada exercício:

- 2020/06 → 225 linhas, 0 com arrecadação > 0.
- 2021/06 → 230 linhas, 0 com arrecadação > 0.
- 2022/06 → 183 linhas, 0 com arrecadação > 0.
- 2023/06 → 353 linhas, 169 com arrecadação > 0 (data_emissao real do recolhimento, ex.: `30/06/2023`).

Ou seja, **o Município Online nunca republicou o histórico arrecadado de 2020–2022** após a migração do portal; só a série 2023+ entra com dados realizados. Por isso, na visualização plurianual “Arrecadação discriminada por receita”, as colunas 2020–2021 aparecem como `—` (nenhuma linha para aquele `cod_item_receita` naquele ano) e 2022 aparece como `R$ 0,00` (linha existe, porém zerada). Esse comportamento é **fiel à fonte**, não um bug de ingestão.

Para preencher 2020–2022 usamos o SICONFI como **fonte complementar**, documentada na seção 6.

### Visões derivadas disponibilizadas pela API
- **Resumo do exercício** (`/api/v1/arrecadacao/resumo?exercicio=`): total arrecadado, LOA atualizada (soma de `MAX(valor_atualizado)` por item+fonte — evita inflação pelo número de meses), % realização, Δ YoY, número de tributos.
- **Séries anuais e mensais** (`/por-exercicio`, `/por-mes`), **por espécie** (`/por-especie`), **top-N tributos** (`/top-tributos`), **matriz ano×espécie** (`/ano-x-especie`).
- **Visão plurianual** (2º painel BI): `/historico/por-receita?ano_inicio=&ano_fim=&limite=` (pivot receita contábil × ano) e `/historico/mes-x-ano?ano_inicio=&ano_fim=` (barras empilhadas mês × ano).

---

## 6. SICONFI / STN — Tesouro Nacional

**Fornecedor**: Secretaria do Tesouro Nacional. API pública ORDS, sem autenticação.
**Escopo coberto pela Lente**: execução orçamentária agregada (RREO), compliance LRF (RGF) e — validado em 04/2026 — **backfill de arrecadação histórica para 2020–2022** quando o Município Online não publica realizado.

### URL base
- `https://apidatalake.tesouro.gov.br/ords/siconfi/tt`
- `id_ente` de Jequié (código IBGE): `2918001`

### Conectores existentes
Conector: `app/connectors/siconfi.py` (métodos `rreo`, `paginar_rreo`, `rgf`, `paginar_rgf`).
Serviços: `app/services/ingestao_orcamento.py` (`ingerir_rreo`, `ingerir_rgf`).
Persistência: tabela `execucao_orcamentaria` (célula bruta com `exercicio × periodo × anexo × cod_conta × coluna`).
Comandos: `make ingest-orcamento ano=AAAA`, `make ingest-rgf ano=AAAA`.

### Feeds relevantes para arrecadação

Endpoint `GET /rreo` (bimestral) e `GET /rgf` (quadrimestral) já estão integrados. Para o gap de arrecadação de 2020–2022, os dois feeds adicionais relevantes são:

#### 6.1. RREO-Anexo 03 (mensal, por item-chave)

*“Demonstrativo da Receita Corrente Líquida”.* Contém a arrecadação **mensal** dos principais tributos e transferências — os mesmos `cod_item_receita` que dominam o top-30 do painel:

- `IPTULiquidoExcetoTransferenciasEFUNDEB` → IPTU
- `ISSLiquidoExcetoTransferenciasEFUNDEB` → ISS/ISSQN
- `ITBILiquidoExcetoTransferenciasEFUNDEB` → ITBI
- `IRRFLiquidoExcetoTransferenciasEFUNDEB` → IRRF
- `RREO3CotaParteDoFPM` → Cota-Parte do FPM
- `RREO3CotaParteDoICMS` → Cota-Parte do ICMS
- `RREO3CotaParteDoIPVA` → Cota-Parte do IPVA

Colunas mensais: `<MR>`, `<MR-1>`, …, `<MR-11>` (últimos 12 meses encerrados no bimestre). Consultando `nr_periodo=6` obtemos `<MR-11>` = janeiro e `<MR>` = dezembro do exercício. Colunas agregadas: `TOTAL (ÚLTIMOS 12 MESES)`, `PREVISÃO ATUALIZADA AAAA`.

Amostra validada (Jequié, 2020/06, ISS): `<MR-11>=1,72 mi` … `<MR>=7,04 mi`, `TOTAL 12 MESES = 26,25 mi`. Disponível para 2020, 2021, 2022 (e demais anos).

**Limitação**: os valores do Anexo 03 são *“Líquidos Exceto Transferências e FUNDEB”* — portanto não batem 1-para-1 com o bruto do Município Online; a diferença é a dedução de FUNDEB (relevante em IPTU, ISS, ITBI, IRRF). Para a visualização plurianual isso é aceitável desde que a origem do dado seja explicitada na coluna (`fonte="SICONFI_RREO3"`) ou o dado seja reconstituído somando a dedução FUNDEB do próprio anexo.

#### 6.2. DCA-Anexo I-C (anual, por cod_conta STN, ampla cobertura)

*“Balanço Orçamentário — Receitas Brutas Realizadas”.* Contém a **arrecadação bruta anual** por `cod_conta` completo do STN. Colunas: `Receitas Brutas Realizadas` e `Deduções - FUNDEB`.

Cobertura validada para Jequié (04/2026):

- 2020 → 117 linhas de receita, soma bruta R$ 4,04 bi (inclui receitas intra-orçamentárias — filtrar por `cod_conta` prefixado `RO`).
- 2021 → 115 linhas, R$ 4,30 bi.
- 2022 → 133 linhas, R$ 5,10 bi (STN reestruturou o PCASP — códigos mudam de `1.1.1.8.*` para `1.1.1.2.*` a partir de 2022).

Mapeamento com o Município Online: DCA usa `cod_conta = "RO1.1.1.8.01.1.0"`; Município Online usa `cod_item_receita = "111801010100"` (12 dígitos). A conversão é: tirar `RO`, remover pontos, zero-pad até 12. Exemplos validados:

- IPTU: DCA `RO1.1.1.8.01.1.0` ↔ MO `111801010100`.
- ISS: DCA `RO1.1.1.8.02.3.0` ↔ MO `111802030000` (2020–2021); DCA `RO1.1.1.4.51.0.0` ↔ `111451000000` (2022+).

**Limitação**: granularidade **anual apenas**. Não alimenta o painel “mês × ano”; alimenta apenas o painel plurianual “por receita × ano”.

### Estratégia de integração proposta
Para fechar o gap sem misturar fontes conflitantes na mesma tabela `arrecadacao`:

1. Adicionar método `dca` no conector SICONFI (análogo a `rreo`).
2. Criar serviço `ingestao_arrecadacao_historica` que consome DCA Anexo I-C e grava em `arrecadacao` usando `fonte="SICONFI_DCA"` e `mes=12` (uma linha anual agregada por item). Manter `fonte="MUNICIPIO_ONLINE"` para 2023+.
3. Na API `/historico/por-receita` unir as duas fontes por ano, preferindo `MUNICIPIO_ONLINE` quando disponível e caindo em `SICONFI_DCA` para 2020–2022.
4. Opcional (fase 2): ingerir RREO Anexo 03 para reconstituir a série mensal dos ~7 itens-chave (FPM, ICMS, ISS, IPTU, ITBI, IRRF, IPVA) em 2020–2022 e alimentar o painel mês × ano retrospectivamente.

Comandos Make sugeridos:
```
make ingest-arrecadacao-dca ano=2020
make ingest-arrecadacao-dca-historico       # 2020..2022
```

### Outras capacidades já cobertas pelo SICONFI
- **RREO Anexo 01** (Balanço Orçamentário): Receita Arrecadada agregada por categoria econômica (Impostos, Taxas, Transferências) — **já ingerido** para 2023–2024; cobertura 2020–2022 disponível no endpoint, pendente de backfill.
- **RGF**: indicadores LRF (dívida consolidada, pessoal, serviço da dívida) — já ingerido.
