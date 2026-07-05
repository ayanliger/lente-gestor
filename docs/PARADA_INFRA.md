# Parada da infraestrutura (2026-07-05)

Este documento registra a desativação completa da infraestrutura do Lente Gestor no Google Cloud, feita para interromper a cobrança no projeto `lente-gestor`. O código da aplicação permanece intacto e a infraestrutura pode ser recriada via Terraform quando necessário.

## O que foi removido

Executou-se `terraform destroy` em `infra/` (29 recursos destruídos), além de remoções diretas via `gcloud`:

- **Cloud SQL `lente-db`**: instância PostgreSQL 16 destruída, incluindo o banco `lente`, o usuário e os backups. Os dados foram perdidos - será preciso rodar as migrações e reingerir os dados na recriação.
- **Cloud Run service `lente-api`**: removido (via `gcloud run services delete`).
- **Cloud Run jobs**: `migrate-db`, `ingest-pncp`, `ingest-orcamento`, `ingest-rgf`, `ingest-ibge` e `ingest-rag` removidos (via `gcloud run jobs delete`).
- **Artifact Registry `us-central1/lente`**: repositório e imagens Docker removidos.
- **Secret Manager**: secrets `lente-database-url` e `lente-app-secret-key` removidos.
- **Service account `lente-api@lente-gestor.iam.gserviceaccount.com`**: removida, junto com os bindings IAM.
- **APIs do projeto**: desabilitadas (Cloud Run, Cloud SQL Admin, Vertex AI, Cloud Build, Artifact Registry, Secret Manager, entre outras).
- **Firebase Hosting**: desabilitado com `firebase hosting:disable` - o site parou de servir o frontend. Basta um novo `firebase deploy` para reativar.

## Alterações no código

- `infra/modules/cloud_run_api/main.tf` e `infra/modules/cloud_run_jobs/main.tf`: adicionado `deletion_protection = false` nos recursos Cloud Run v2. O provider Google (>= 6.0) habilita essa proteção por padrão e bloqueia o `terraform destroy` sem ela. Manter o valor em `false` enquanto o projeto for protótipo.
- O estado local do Terraform (`infra/terraform.tfstate`) ficou vazio de recursos após o destroy.

## Como reativar o projeto

1. Habilitar o billing e conferir o projeto ativo: `gcloud config set project lente-gestor`.
2. Recriar a infraestrutura: `terraform -chdir=infra apply` (as APIs são reabilitadas pelo módulo `apis`).
3. Rebuild e deploy do backend: `gcloud builds submit --config cloudbuild.yaml` (roda build, push, deploy do service, atualização dos jobs e a migração `migrate-db`).
4. Reingerir os dados executando os jobs: `gcloud run jobs execute ingest-pncp` (e os demais: `ingest-orcamento`, `ingest-rgf`, `ingest-ibge`, `ingest-rag`), todos com `--region=us-central1`.
5. Redeploy do frontend: `cd frontend && npm run build && firebase deploy --only hosting`.
