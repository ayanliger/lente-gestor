/**
 * Repositório Docker em Artifact Registry para hospedar a imagem do backend.
 */

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "repository_id" {
  type    = string
  default = "lente"
}

resource "google_artifact_registry_repository" "lente" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Imagens Docker do Lente Gestor (backend FastAPI + jobs)."
  format        = "DOCKER"
}

output "repository" {
  description = "Caminho canônico do repositório (sem tag)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.lente.repository_id}"
}

output "repository_id" {
  value = google_artifact_registry_repository.lente.repository_id
}
