/**
 * Terraform root para o deploy do Lente Gestor no Google Cloud.
 *
 * Ordem lógica dos módulos:
 *   1. apis               → habilita serviços GCP necessários
 *   2. service_accounts   → cria SA da API com roles mínimos
 *   3. artifact_registry  → repositório Docker para imagens do backend
 *   4. database           → Cloud SQL PG16 + pgvector + usuário
 *   5. secrets            → DATABASE_URL e APP_SECRET_KEY no Secret Manager
 *   6. cloud_run_api      → serviço público da API (FastAPI)
 *   7. cloud_run_jobs     → jobs para migrate-db e ingestões
 *
 * Firebase Hosting é configurado fora do Terraform (via firebase CLI),
 * por simplicidade e porque o provider para Hosting é limitado.
 */

terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ──────────────────────────────────────────────────────────────────────
# Módulos
# ──────────────────────────────────────────────────────────────────────

module "apis" {
  source     = "./modules/apis"
  project_id = var.project_id
}

module "service_accounts" {
  source     = "./modules/service_accounts"
  project_id = var.project_id

  depends_on = [module.apis]
}

module "artifact_registry" {
  source     = "./modules/artifact_registry"
  project_id = var.project_id
  region     = var.region

  depends_on = [module.apis]
}

module "database" {
  source     = "./modules/database"
  project_id = var.project_id
  region     = var.region
  zone       = var.zone

  depends_on = [module.apis]
}

module "secrets" {
  source       = "./modules/secrets"
  project_id   = var.project_id
  database_url = module.database.database_url

  depends_on = [module.apis]
}

module "cloud_run_api" {
  source                   = "./modules/cloud_run_api"
  project_id               = var.project_id
  region                   = var.region
  service_account_email    = module.service_accounts.email
  image                    = var.api_image
  cloudsql_connection_name = module.database.connection_name
  database_url_secret      = module.secrets.database_url_id
  app_secret_key_secret    = module.secrets.app_secret_key_id
  cors_origins             = var.cors_origins

  depends_on = [module.apis, module.secrets, module.service_accounts]
}

module "cloud_run_jobs" {
  source                   = "./modules/cloud_run_jobs"
  project_id               = var.project_id
  region                   = var.region
  service_account_email    = module.service_accounts.email
  image                    = var.api_image
  cloudsql_connection_name = module.database.connection_name
  database_url_secret      = module.secrets.database_url_id
  app_secret_key_secret    = module.secrets.app_secret_key_id
  exercicio_fiscal         = var.exercicio_fiscal

  depends_on = [module.apis, module.secrets, module.service_accounts]
}
