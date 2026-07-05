/**
 * Cloud Run v2 Service: lente-api
 *
 *  - min_instance_count = 0  → escala a zero (custo mínimo para protótipo)
 *  - max_instance_count = 5  → limite de segurança
 *  - Memória 512Mi, 1 vCPU   → suficiente para FastAPI + asyncpg + genai
 *  - Cloud SQL montado automaticamente em /cloudsql/CONN_NAME
 *  - --allow-unauthenticated via IAM binding a allUsers (prototipagem)
 *  - Secrets montados como env vars (DATABASE_URL, APP_SECRET_KEY)
 *
 * Lifecycle: ignora mudanças na imagem feitas fora do Terraform (CI/CD via
 * `gcloud run deploy` sobrepõe a imagem; não queremos TF revertendo).
 */

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_name" {
  type    = string
  default = "lente-api"
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

variable "cors_origins" {
  type    = string
  default = ""
}

variable "gcp_location_embed" {
  type    = string
  default = "us-central1"
}

variable "gcp_location_generate" {
  type    = string
  default = "global"
}

resource "google_cloud_run_v2_service" "lente_api" {
  project  = var.project_id
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  deletion_protection = false

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    # Cloud SQL é montado automaticamente pelo Cloud Run em
    # /cloudsql/CONN_NAME — precisa estar declarado como volume no template.
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.cloudsql_connection_name]
      }
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8080
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      # ── Secrets
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

      # ── Configuração de ambiente
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
        value = var.gcp_location_embed
      }

      env {
        name  = "GCP_LOCATION_GENERATE"
        value = var.gcp_location_generate
      }

      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 6
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 60
        timeout_seconds   = 5
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      # A imagem é atualizada pelo CI/CD (`gcloud run deploy`); TF não deve reverter.
      template[0].containers[0].image,
    ]
  }
}

# Acesso público (protótipo). Para remover acesso público depois:
#   substituir "allUsers" por um grupo específico / Firebase Auth.
resource "google_cloud_run_v2_service_iam_binding" "public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.lente_api.location
  name     = google_cloud_run_v2_service.lente_api.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}

output "url" {
  value = google_cloud_run_v2_service.lente_api.uri
}

output "name" {
  value = google_cloud_run_v2_service.lente_api.name
}
