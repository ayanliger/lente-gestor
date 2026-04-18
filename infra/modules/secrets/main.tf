/**
 * Secret Manager: DATABASE_URL e APP_SECRET_KEY.
 * A SA `lente-api` já tem `roles/secretmanager.secretAccessor` (no módulo
 * service_accounts), então não precisa de IAM binding por-secret aqui.
 */

variable "project_id" {
  type = string
}

variable "database_url" {
  type      = string
  sensitive = true
}

# 48 chars hex = 192 bits. Suficiente para JWT signing etc.
resource "random_password" "app_secret_key" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "lente-database-url"

  replication {
    auto {}
  }

  labels = {
    app       = "lente-gestor"
    component = "backend"
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = var.database_url
}

resource "google_secret_manager_secret" "app_secret_key" {
  project   = var.project_id
  secret_id = "lente-app-secret-key"

  replication {
    auto {}
  }

  labels = {
    app       = "lente-gestor"
    component = "backend"
  }
}

resource "google_secret_manager_secret_version" "app_secret_key" {
  secret      = google_secret_manager_secret.app_secret_key.id
  secret_data = random_password.app_secret_key.result
}

# ──────────────────────────────────────────────────────────────────────

output "database_url_id" {
  value = google_secret_manager_secret.database_url.secret_id
}

output "app_secret_key_id" {
  value = google_secret_manager_secret.app_secret_key.secret_id
}
