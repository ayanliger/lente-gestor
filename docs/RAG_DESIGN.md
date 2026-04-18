# RAG — Decisões de Design (Fase 1)
> **Status:** Em desenvolvimento — Fase 1 implementada.
> **Escopo desta fase:** backend completo (modelo, indexador, retrieval, geração, `/chat`), frontend mínimo (página `/assistente`), auto-reindex por fonte, golden set de 10 perguntas, testes unitários + integração contra Vertex AI.
---
## 1. Truncamento Matryoshka a 1536 dimensões
**Decisão.** Os embeddings do `gemini-embedding-2-preview` são gerados com `output_dimensionality=1536`, não os 3072 nativos.
**Por quê.** O índice HNSW do `pgvector` em colunas `vector` tem limite nativo de 2000 dimensões. Com 3072 dims, precisaríamos (a) viver sem índice (scan linear a cada busca) ou (b) usar `halfvec(3072)` com meia precisão. Matryoshka é suportado oficialmente pela família Gemini Embedding e preserva quase toda a qualidade ao truncar, sem complicações de tipo.
**Reversibilidade.** Se qualidade se provar insuficiente, migrar para `halfvec(3072)` é mudança localizada: apenas a coluna `embedding` + o índice + o valor de `gemini_embedding_dimensions` em `Settings`. `modelo_embedding` em cada linha (`gemini-embedding-2-preview@1536`) identifica qual modelo+dim gerou o vetor, permitindo migração gradual.
## 2. Stateless no MVP (sem histórico/sessão/auth)
**Decisão.** `POST /chat` é stateless. Nenhum histórico, nenhuma sessão, nenhuma autenticação.
**Por quê.** Cada uma dessas features carrega decisões de schema, segurança e custo que não se resolvem trivialmente. No MVP, o valor está em **provar que a pergunta + corpus + resposta com citação funciona**. Conversa multi-turn fica para quando o uso real mostrar que é necessário (e o log estruturado por request, ADR 6, vai mostrar).
**Risco aceito.** Quem quiser "contexto de pergunta anterior" precisa repetir no texto da nova pergunta. Pela frequência de uso esperada (painel de gestor, não chatbot), é aceitável.
## 3. `task_type` assimétrico: `RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY`
**Decisão.** Documentos são embedados com `task_type="RETRIEVAL_DOCUMENT"` na indexação; perguntas com `task_type="RETRIEVAL_QUERY"` na busca.
**Por quê.** Modelos de embedding treinados com objetivo "dual encoder" (é o caso do Gemini Embedding 2) produzem representações diferentes para o mesmo texto conforme o task_type — essa assimetria melhora o recall significativamente, particularmente em queries curtas vs documentos longos. Usar o mesmo task_type para ambos descarta ganho conhecido com custo zero.
**Validação.** Teste de integração `test_task_type_assimetrico_produz_vetores_diferentes` confirma que o mesmo texto produz vetores distintos entre os dois task_types.
## 4. Limiar de similaridade cosseno 0.5
**Decisão.** Documentos com similaridade cosseno abaixo de `settings.rag_limiar_similaridade` (padrão 0.5) são descartados antes do prompt.
**Por quê.** Entrar no prompt com documentos fracos dilui o contexto e aumenta a chance de citação de algo irrelevante. 0.5 é um limiar conservador que empiricamente (na literatura de RAG) separa sinal de ruído sem ser agressivo demais.
**Ajustabilidade.** Exposto como `Settings.rag_limiar_similaridade`. Se o eval começar a ter muita recusa falso-positiva (modelo dizendo `NAO_SEI` porque nada passou do limiar), baixar para 0.4 é o primeiro ajuste.
## 5. Política de recusa via marcador `NAO_SEI`
**Decisão.** O system prompt força o modelo a responder apenas a palavra `NAO_SEI` quando os documentos recuperados não respaldam uma resposta confiável. A rota converte isso em `RespostaChat(recusou=True, fontes=[])`.
**Por quê.** O princípio estrutural do produto é **sem fonte, sem resposta**. Sem um marcador explícito, modelos tendem a inventar ou recorrer a conhecimento geral — o que destrói a confiança do gestor na ferramenta. Um marcador único e fácil de detectar no pós-processamento dá controle duro sobre a política.
**Defense in depth.** Se o modelo retornar texto com `NAO_SEI` misturado com outra coisa (ex: "Não tenho certeza, mas NAO_SEI exatamente"), a detecção é por substring → vira recusa. Melhor recusar um caso marginal do que deixar passar uma alucinação.
## 6. Thinking ativado + temperatura 1.0
**Decisão.** `thinking_config.thinking_budget=-1` (orçamento dinâmico, modelo decide) e `temperature=1.0`.
**Por quê.** A **thinking é onde o produto ganha valor de verdade**. O cruzamento PCA × execução, ou LRF × contratos por função, exige alinhar dois documentos no mesmo eixo antes de responder — operação não-trivial que o thinking faz bem. A temperatura 1.0 é a recomendada oficialmente pela Google para o Gemini 3.1 Pro quando thinking está ativado; temperaturas baixas podem prejudicar a qualidade do raciocínio.
**Custo.** Thinking consome tokens adicionais (incluídos no `uso_tokens.thinking` que logamos em cada request). Vale a pena: o cruzamento é o diferencial da Lente. Rate limit + auditoria de tokens por request controlam o risco.
## 7. Auto-reindex síncrono por fonte após ingestão de negócio
**Decisão.** Cada script de ingestão de negócio (`ingest_pncp`, `ingest_orcamento`, `ingest_rgf`) dispara, ao fim do seu trabalho, a reindexação RAG **síncrona** das fontes afetadas. Flag `--sem-reindex` opta out.
**Mapeamento:**
| Script | Fontes RAG reindexadas |
| --- | --- |
| `ingest_pncp` | `CONTRATO`, `RESUMO_PCA` |
| `ingest_orcamento` | `RESUMO_FUNCAO` |
| `ingest_rgf` (com indicadores derivados) | `INDICADOR_FISCAL` |
| `ingest_ibge` | *(nada nesta fase; `DadosMunicipio` fica para Fase 2)* |
**Por quê síncrono.** Determinismo — o script termina quando a base RAG está coerente com o que foi ingerido. Facilita uso em Cloud Run Jobs na fase de deploy. E o custo é tipicamente segundos: o skip por hash faz com que só o que mudou seja embedado de novo.
**Política de falha.** Reindex que falhe **não reverte** a ingestão de negócio (que já commitou). Script sai com exit code ≠ 0 e loga erro estruturado `rag.auto_reindex.falhou`; operador corre `make ingest-rag` manualmente para recuperar. Princípio: **ingestão é fato, indexação é derivada**.
## 8. Log estruturado por request (`chat.request`)
**Decisão.** Cada chamada ao `/chat` emite um único evento `structlog` com: pergunta, docs recuperados (com scores), docs usados, texto da resposta, citações extraídas, recusou, latência total + 3 legs (embed, busca, gen), uso de tokens (`prompt`, `output`, `thinking`), `request_id`.
**Por quê.** Debug + eval ao mesmo tempo. Quando algo estranho acontece em produção, o log tem tudo que se precisa para entender. E é **matéria-prima natural para expandir o golden set**: perguntas reais do gestor → curadoria → adicionadas ao YAML.
## 9. Golden set de 10 perguntas como eval inicial
**Decisão.** 10 perguntas canônicas em `backend/tests/rag/golden_set.yaml`, rodadas pelo `test_rag_integracao.py::test_golden_set` contra o corpus real indexado.
**Distribuição deliberada:** 3 PCA × execução (cruzamento flagship), 2 LRF puras, 2 contratos específicos, 2 cruzamento LRF × contratos (thinking), 1 recusa esperada.
**Critérios estruturais (não textuais).**
- **Recall@6 ≥ 50%** das chaves esperadas para perguntas respondíveis
- **≥1 citação** na resposta quando não há recusa
- **Recusa efetiva** (`recusou=True`) para a pergunta cujo dado não está no corpus
Determinismo textual de LLM é mentira — por isso nenhum assert em conteúdo exato da resposta.
**Evolução.** Cresce com base nos logs `chat.request`: perguntas reais → curadas pelo time → adicionadas ao YAML com `chaves_esperadas_top6` preenchido após rodar uma vez em produção.
