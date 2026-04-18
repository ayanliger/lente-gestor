"""Configuração da aplicação via variáveis de ambiente."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas do .env ou variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Aplicação
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Banco de dados
    database_url: str = "postgresql+asyncpg://lente:lente_dev@localhost:5432/lente"

    # PNCP
    pncp_base_url: str = "https://pncp.gov.br/api/consulta/v1"
    pncp_cnpj_jequie: str = "13894878000160"

    # SICONFI (Tesouro Nacional)
    siconfi_base_url: str = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
    siconfi_id_ente_jequie: str = "2918001"  # código IBGE de Jequié - BA

    # IBGE
    ibge_base_url: str = "https://servicodados.ibge.gov.br/api"

    # Google Cloud / Gemini (RAG)
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_embedding_model: str = "gemini-embedding-2-preview"
    # Dimensão Matryoshka-truncada: permite HNSW no pgvector (limite de 2000 dims
    # em `vector`). Se mudar, rodar migração nova para ajustar a coluna/índice.
    gemini_embedding_dimensions: int = 1536

    # RAG
    # Limiar de similaridade cosseno mínimo para incluir documento no prompt
    # (0 = equivalente, 1 = ortogonal). Com <=>, similaridade = 1 - distance.
    rag_limiar_similaridade: float = 0.5
    # Rate limit do endpoint /chat (formato slowapi, ex: "20/minute").
    rate_limit_chat: str = "20/minute"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
