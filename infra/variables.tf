variable "project_id" {
  type        = string
  description = "ID do projeto GCP onde o Lente Gestor é implantado."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Região principal dos recursos (Cloud Run, Cloud SQL, Artifact Registry)."
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "Zona para recursos zonais (instância do Cloud SQL)."
}

variable "api_image" {
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
  description = <<EOT
Imagem Docker do backend. Default é placeholder "hello world" do Google Cloud Run
para permitir o primeiro `terraform apply` antes de existir uma imagem real.
Após o primeiro build (`gcloud builds submit --config cloudbuild.yaml`), a CI atualiza
o Cloud Run Service e os Jobs via `gcloud run deploy`/`gcloud run jobs update`.
Se preferir pinar aqui, use:
  "us-central1-docker.pkg.dev/<project>/lente/api:<sha>"
EOT
}

variable "cors_origins" {
  type        = string
  default     = ""
  description = <<EOT
Origens permitidas para CORS, separadas por vírgula.
Deixe vazio no primeiro apply (antes do Firebase Hosting existir) e preencha depois
com a URL publicada (ex: "https://lente-gestor.web.app,https://lente-gestor.firebaseapp.com").
EOT
}

variable "exercicio_fiscal" {
  type        = number
  default     = 2024
  description = "Exercício fiscal default para os jobs de ingestão de orçamento/RGF."
}
