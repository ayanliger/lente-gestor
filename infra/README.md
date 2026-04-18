# Infraestrutura — Lente Gestor no Google Cloud

Terraform que provisiona todo o stack de execução do **Lente Gestor** no GCP:
Cloud Run (API + Jobs), Cloud SQL PG16 + pgvector, Secret Manager, Artifact
Registry, Service Accounts e APIs habilitadas.

O frontend (Firebase Hosting) é configurado **fora** do Terraform, via
`firebase.json` em `frontend/`.

## Estrutura

```
infra/
├── main.tf                        # Compõe todos os módulos
├── variables.tf / outputs.tf      # Entradas/saídas do root
├── terraform.tfvars.example       # Template — copie para terraform.tfvars
└── modules/
    ├── apis/                      # Habilita services (run, sqladmin, aiplatform, ...)
    ├── service_accounts/          # SA `lente-api` com roles mínimos
    ├── artifact_registry/         # Repositório Docker `lente`
    ├── database/                  # Cloud SQL PG16 + pgvector
    ├── secrets/                   # DATABASE_URL, APP_SECRET_KEY
    ├── cloud_run_api/             # Service `lente-api` (FastAPI)
    └── cloud_run_jobs/            # migrate-db, ingest-pncp, ingest-*, ingest-rag
```

## Pré-requisitos

- `terraform >= 1.7`
- `gcloud` autenticado (`gcloud auth application-default login`)
- Projeto GCP com faturamento habilitado (os créditos cobrem o protótipo)
- Papel `roles/owner` ou `roles/editor` + `roles/iam.securityAdmin` na conta
  que roda o Terraform

## Bootstrap (primeira vez)

```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# (Opcional) editar terraform.tfvars para ajustar região, zona, etc.

terraform init
terraform apply
```

No primeiro apply:

- `api_image` usa um placeholder (`us-docker.pkg.dev/cloudrun/container/hello`).
  O Cloud Run sobe com a "hello world" do Google só para ter a URL estável.
- Cloud SQL leva **~10 minutos** para provisionar.
- As APIs habilitam em ~1 minuto.

## Build + deploy da imagem real

Após o `terraform apply`:

```bash
# Na raiz do repositório (não dentro de infra/)
cd ..
gcloud builds submit --config cloudbuild.yaml
```

Isso faz:

1. Build da imagem a partir de `backend/Dockerfile`
2. Push para `us-central1-docker.pkg.dev/lente-gestor/lente/api:<sha>`
3. `gcloud run services update lente-api --image=...` → nova imagem no Service
4. Atualiza a imagem de todos os Cloud Run Jobs (migrate-db, ingest-*)
5. Executa `migrate-db` com `--wait` (aplica as migrações Alembic)

Depois disso, a API responde em:

```
https://lente-api-<hash>-uc.a.run.app/health
```

## Executar ingestões

```bash
gcloud run jobs execute ingest-ibge       --region us-central1 --wait
gcloud run jobs execute ingest-pncp       --region us-central1 --wait
gcloud run jobs execute ingest-orcamento  --region us-central1 --wait
gcloud run jobs execute ingest-rgf        --region us-central1 --wait
gcloud run jobs execute ingest-rag        --region us-central1 --wait
```

Os três primeiros podem rodar em paralelo (fontes distintas). `ingest-rag`
deve rodar **por último**, porque ele indexa o que os outros ingeriram.

> **Tip:** o exercício fiscal default (2024) está em `variables.tf`
> (`var.exercicio_fiscal`). Para mudar:
> ```bash
> gcloud run jobs update ingest-orcamento --region us-central1 \
>     --args='-m,scripts.ingest_orcamento,--exercicio,2025'
> ```
> Ou re-aplicar o Terraform com `-var exercicio_fiscal=2025`.

## Frontend (Firebase Hosting)

```bash
cd frontend/
npm install
npm run build

# Primeira vez: logar e configurar site
firebase login
firebase use lente-gestor
# (cria site default se não existir — pode rodar `firebase projects:list` antes)

firebase deploy --only hosting
```

URL final: `https://lente-gestor.web.app` (ou `…firebaseapp.com`).

Após publicar, adicione a URL ao `CORS_ORIGINS`:

```bash
terraform apply -var='cors_origins=https://lente-gestor.web.app,https://lente-gestor.firebaseapp.com'
```

Ou edite `terraform.tfvars` e re-aplique.

## Outputs úteis

```bash
terraform output api_url                     # URL do Cloud Run
terraform output api_service_account         # e-mail da SA
terraform output artifact_registry_repository # caminho do repositório
terraform output cloudsql_connection_name    # PROJECT:REGION:INSTANCE
terraform output jobs                        # mapa dos jobs criados
```

## Custos esperados (us-central1, créditos GCP)

| Recurso                    | Custo mensal aprox. |
|----------------------------|---------------------|
| Cloud SQL `db-g1-small`    | ~US$25              |
| Cloud Run (idle/low usage) | ~US$0–5             |
| Artifact Registry (10GB)   | ~US$1               |
| Secret Manager             | ~US$0               |
| Firebase Hosting           | US$0 (free tier)    |
| Vertex AI (Gemini)         | pay-per-request     |

Total base: **~US$25–30/mês**, quase tudo no Cloud SQL. Escalar para
`db-custom-1-3840` ou `db-custom-2-7680` se o volume crescer.

## Destruir tudo (cuidado)

```bash
terraform destroy
```

Antes de destruir, considere:

1. Backup manual do banco (`gcloud sql backups create`)
2. Remover `deletion_protection = false` em `modules/database/main.tf` se a
   instância já não for protótipo

## Troubleshooting

**"Error 403: Permission 'cloudsql.instances.connect' denied"** na API
↳ Verificar que a SA tem `roles/cloudsql.client` (módulo `service_accounts`).

**"permission denied for extension vector"** na migração
↳ Verificar que o flag `cloudsql.enable_pgvector = on` está ativo
  (`gcloud sql instances describe lente-db --format="value(settings.databaseFlags)"`).

**"connection refused" no startup do Cloud Run**
↳ A sintaxe da `DATABASE_URL` precisa ser exatamente
  `postgresql+asyncpg://user:pass@/lente?host=/cloudsql/PROJECT:REGION:INSTANCE`.
  Verifique via `gcloud secrets versions access latest --secret=lente-database-url`.

**Cold start lento (>10s)**
↳ Esperado com `min_instance_count=0`. Subir para 1 se for vital para apresentação:
  ```
  gcloud run services update lente-api --region us-central1 --min-instances=1
  ```
