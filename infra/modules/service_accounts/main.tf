/**
 * Service account usada pelo Cloud Run Service (API) e pelos Cloud Run Jobs.
 * Roles concedidos:
 *   - cloudsql.client         → conectar ao Cloud SQL via proxy nativo
 *   - aiplatform.user         → chamar Gemini via Vertex AI (RAG)
 *   - secretmanager.secretAccessor → ler DATABASE_URL e APP_SECRET_KEY
 *   - logging.logWriter       → emitir logs estruturados (structlog)
 *   - monitoring.metricWriter → métricas do Cloud Monitoring
 */

variable "project_id" {
  type = string
}

variable "account_id" {
  type    = string
  default = "lente-api"
}

resource "google_service_account" "lente_api" {
  project      = var.project_id
  account_id   = var.account_id
  display_name = "Lente API runtime service account"
  description  = "SA usada pelo Cloud Run service e pelos Jobs do Lente Gestor."
}

locals {
  roles = [
    "roles/cloudsql.client",
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ]
}

resource "google_project_iam_member" "lente_api" {
  for_each = toset(local.roles)

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.lente_api.email}"
}

output "email" {
  value = google_service_account.lente_api.email
}

output "id" {
  value = google_service_account.lente_api.id
}
