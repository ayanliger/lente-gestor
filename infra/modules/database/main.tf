/**
 * Cloud SQL PostgreSQL 16 com pgvector habilitado.
 *
 * Decisões:
 *  - Tier `db-g1-small` (1 vCPU compartilhada, 1.7Gi RAM). Suficiente para
 *    protótipo com ~milhares de embeddings. Escalar via TF depois.
 *  - Zonal (não regional), para custo. Backup diário 03:00 UTC.
 *  - Conexão via Unix socket em /cloudsql (Cloud Run native). Sem VPC.
 *  - Flag cloudsql.enable_pgvector = on habilita a extensão no nível da
 *    instância (necessário antes do CREATE EXTENSION nas migrações).
 *
 * Extensões `unaccent` e `uuid-ossp` não precisam de flag; são criadas pelas
 * próprias migrações Alembic ou pelo migrate-db job.
 */

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "db_name" {
  type    = string
  default = "lente"
}

variable "db_user" {
  type    = string
  default = "lente"
}

variable "tier" {
  type    = string
  default = "db-g1-small"
}

# Senha forte gerada pelo Terraform. Usa apenas chars URL-safe para que a
# DATABASE_URL não precise de percent-encoding no password.
resource "random_password" "db" {
  length           = 40
  special          = true
  override_special = "_-"
  min_upper        = 4
  min_lower        = 4
  min_numeric      = 4
}

resource "google_sql_database_instance" "lente" {
  project          = var.project_id
  name             = "lente-db"
  region           = var.region
  database_version = "POSTGRES_16"

  # Para protótipo. Em produção: true.
  deletion_protection = false

  settings {
    tier              = var.tier
    # ENTERPRISE suporta tiers shared-core (db-f1-micro, db-g1-small) e
    # custom/standard/highmem. ENTERPRISE_PLUS só aceita db-perf-optimized-*
    # e é o default em projetos novos no GCP — por isso pinamos aqui.
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 10
    disk_autoresize   = true

    location_preference {
      zone = var.zone
    }

    # pgvector é habilitado com `CREATE EXTENSION vector` pela migration RAG
    # (app/db/migrations/versions/a1f7e0b2c3d4_rag_documentos.py). Não precisa
    # de flag ao nível da instância no Cloud SQL PostgreSQL 16+.

    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }

    ip_configuration {
      ipv4_enabled = true
      # Sem private IP por enquanto; Cloud Run usa Unix socket sempre.
      # Se quiser expor a DB para desenvolvimento, adicionar authorized_networks.
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = false
      record_client_address   = false
    }

    maintenance_window {
      day          = 7 # domingo
      hour         = 4 # 04:00 UTC
      update_track = "stable"
    }
  }
}

resource "google_sql_database" "lente" {
  project  = var.project_id
  instance = google_sql_database_instance.lente.name
  name     = var.db_name
}

resource "google_sql_user" "lente" {
  project  = var.project_id
  instance = google_sql_database_instance.lente.name
  name     = var.db_user
  password = random_password.db.result
}

# ──────────────────────────────────────────────────────────────────────
# Outputs
# ──────────────────────────────────────────────────────────────────────

output "connection_name" {
  description = "Connection name (PROJECT:REGION:INSTANCE) para Cloud SQL Auth Proxy."
  value       = google_sql_database_instance.lente.connection_name
}

output "instance_name" {
  value = google_sql_database_instance.lente.name
}

output "database_name" {
  value = google_sql_database.lente.name
}

output "user" {
  value = google_sql_user.lente.name
}

# DATABASE_URL pronta para asyncpg via Unix socket do Cloud Run.
# Formato: postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/CONN_NAME
output "database_url" {
  description = "Connection string para o Secret Manager."
  sensitive   = true
  value       = "postgresql+asyncpg://${google_sql_user.lente.name}:${random_password.db.result}@/${google_sql_database.lente.name}?host=/cloudsql/${google_sql_database_instance.lente.connection_name}"
}
