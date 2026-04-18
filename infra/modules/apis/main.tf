/**
 * Habilita as APIs do GCP que o Lente Gestor precisa.
 * aiplatform e firebase... são obrigatórias para RAG (Vertex AI) e Hosting.
 */

variable "project_id" {
  type = string
}

variable "apis" {
  type = list(string)
  default = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "servicenetworking.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(var.apis)

  project = var.project_id
  service = each.key

  # Para não quebrar outros usos do projeto se o Terraform for destruído
  disable_on_destroy         = false
  disable_dependent_services = false
}
