-- Habilitar extensão pgvector para embeddings (RAG)
CREATE EXTENSION IF NOT EXISTS vector;

-- Extensão para UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extensão para busca textual em português
CREATE EXTENSION IF NOT EXISTS unaccent;
