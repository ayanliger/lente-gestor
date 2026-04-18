output "api_url" {
  description = "URL pública do Cloud Run service (backend)."
  value       = module.cloud_run_api.url
}

output "api_service_account" {
  description = "E-mail da service account usada pelo Cloud Run e pelos Jobs."
  value       = module.service_accounts.email
}

output "artifact_registry_repository" {
  description = "Caminho do repositório Docker (use como prefixo da tag da imagem)."
  value       = module.artifact_registry.repository
}

output "cloudsql_connection_name" {
  description = "Connection name da instância Cloud SQL (PROJECT:REGION:INSTANCE)."
  value       = module.database.connection_name
}

output "database_url_secret" {
  description = "ID do Secret Manager com a DATABASE_URL completa."
  value       = module.secrets.database_url_id
}

output "jobs" {
  description = "Mapa nome → full resource name dos Cloud Run Jobs."
  value       = module.cloud_run_jobs.jobs
}
