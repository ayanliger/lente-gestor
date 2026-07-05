/**
 * Cloud Run Jobs que reutilizam a imagem do backend.
 * Cada job sobrescreve o `command` do container para rodar um script
 * específico (migração ou ingestão). Todos compartilham o mesmo acesso
 * a Cloud SQL e aos secrets.
 */

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "image" {
  type = string
}

variable "cloudsql_connection_name" {
  type = string
}

variable "database_url_secret" {
  type = string
}

variable "app_secret_key_secret" {
  type = string
}

variable "exercicio_fiscal" {
  type    = number
  default = 2024
}

locals {
  # Timeouts foram calibrados para volumes pequenos/médios (Jequié).
  # Ajustar se os pipelines crescerem ou forem estendidos para mais municípios.
  jobs = {
    "migrate-db" = {
      command = ["alembic"]
      args    = ["upgrade", "head"]
      timeout = "600s"
      memory  = "512Mi"
    }
    "ingest-pncp" = {
      command = ["python"]
      # Janela de 6 meses: janelas maiores fazem o PNCP time-out consistentemente
      # (mesmo com retries). Ajustar `--desde`/`--ate` manualmente quando for
      # rodar outra janela.
      args    = ["-m", "scripts.ingest_pncp", "--desde", "2025-01-01", "--ate", "2025-06-30"]
      timeout = "3600s"
      memory  = "1Gi"
    }
    "ingest-orcamento" = {
      command = ["python"]
      args    = ["-m", "scripts.ingest_orcamento", "--exercicio", tostring(var.exercicio_fiscal)]
      timeout = "1800s"
      memory  = "1Gi"
    }
    "ingest-rgf" = {
      command = ["python"]
      args    = ["-m", "scripts.ingest_rgf", "--exercicio", tostring(var.exercicio_fiscal)]
      timeout = "1800s"
      memory  = "1Gi"
    }
    "ingest-ibge" = {
      command = ["python"]
      args    = ["-m", "scripts.ingest_ibge"]
      timeout = "1800s"
      memory  = "512Mi"
    }
    "ingest-rag" = {
      command = ["python"]
      args    = ["-m", "scripts.ingest_rag"]
      timeout = "3600s"
      memory  = "1Gi"
    }
  }
}

resource "google_cloud_run_v2_job" "jobs" {
  for_each = local.jobs

  project  = var.project_id
  name     = each.key
  location = var.region

  deletion_protection = false

  template {
    template {
      service_account = var.service_account_email
      timeout         = each.value.timeout
      max_retries     = 1

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [var.cloudsql_connection_name]
        }
      }

      containers {
        image   = var.image
        command = each.value.command
        args    = each.value.args

        resources {
          limits = {
            cpu    = "1"
            memory = each.value.memory
          }
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = var.database_url_secret
              version = "latest"
            }
          }
        }

        env {
          name = "APP_SECRET_KEY"
          value_source {
            secret_key_ref {
              secret  = var.app_secret_key_secret
              version = "latest"
            }
          }
        }

        env {
          name  = "APP_ENV"
          value = "production"
        }

        env {
          name  = "APP_DEBUG"
          value = "false"
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "GCP_LOCATION"
          value = "us-central1"
        }

        env {
          name  = "GCP_LOCATION_GENERATE"
          value = "global"
        }
      }
    }
  }

  lifecycle {
    # Imagem é atualizada pelo CI/CD; comando/args ficam com o Terraform.
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

output "jobs" {
  value = {
    for k, v in google_cloud_run_v2_job.jobs : k => v.name
  }
}
