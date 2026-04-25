"""Configuração da aplicação via variáveis de ambiente."""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas do .env ou variáveis de ambiente."""

    # Procura o `.env` em dois lugares:
    # 1. CWD (quando rodam direto, ex: `cd backend && python -m ...`)
    # 2. Raiz do repo (um nível acima, layout padrão do monorepo)
    # O primeiro que existir ganha; `.env` no CWD sobrescreve o da raiz.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        # O .env tem vars usadas por docker-compose (POSTGRES_*) e pelo
        # frontend (VITE_*) que não são do escopo do Settings — ignora.
        extra="ignore",
    )

    # Aplicação
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    # Origens CORS permitidas. Em produção vem da URL do Firebase Hosting.
    # Aceita CSV (default) ou JSON list. `NoDecode` pula o decode automático
    # do pydantic-settings (que tentaria JSON em tipo complexo) para que o
    # nosso `_parse_cors_origins` consiga processar o formato CSV simples.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

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

    # Portal de Transparência (Município Online)
    # Fonte do painel de arrecadação tributária. URL concatena base + slug
    # + path da página de receita (ex: `ba/prefeitura/jequie/cidadao/receita`).
    municipio_online_base_url: str = "https://municipioonline.com.br"
    municipio_online_slug_jequie: str = "ba/prefeitura/jequie"

    # Google Cloud / Gemini (RAG)
    gcp_project_id: str = ""
    # Região do endpoint de embeddings. `gemini-embedding-2-preview` é servido
    # em endpoints regionais (ex: us-central1).
    gcp_location: str = "us-central1"
    # Região do endpoint de geração. Modelos Gemini 3.1 em preview são
    # servidos **apenas** via `global`; a 2.5 pro/flash funciona em ambos.
    # Mantemos como config separada pra permitir flexibilidade.
    gcp_location_generate: str = "global"
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_embedding_model: str = "gemini-embedding-2-preview"
    # Dimensão Matryoshka-truncada: permite HNSW no pgvector (limite de 2000 dims
    # em `vector`). Se mudar, rodar migração nova para ajustar a coluna/índice.
    gemini_embedding_dimensions: int = 1536

    # RAG
    # Limiar de similaridade cosseno: docs acima entram no prompt "sem reservas".
    # Não é barreira de acesso — se nenhum doc passar, o retrieval ainda
    # garante `rag_fallback_minimo` documentos (os top-K por score). Ideia:
    # nunca mandar prompt vazio; deixar o modelo decidir quando recusar.
    rag_limiar_similaridade: float = 0.3
    # Quantos docs passar pro prompt mesmo quando todos estão abaixo do limiar.
    rag_fallback_minimo: int = 3
    # Rate limit do endpoint /chat (formato slowapi, ex: "20/minute").
    rate_limit_chat: str = "20/minute"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Aceita CSV (conveniente em env var do Cloud Run) ou lista JSON."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            # Se vier como JSON list, deixa o pydantic parsear normalmente
            if stripped.startswith("["):
                return value
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
