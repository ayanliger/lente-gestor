"""
Modelo para a camada RAG — documentos indexáveis com embedding.

Um `DocumentoRag` representa uma unidade de informação navegável (contrato,
indicador fiscal, resumo por função, resumo por PCA). Cada linha carrega:

- `conteudo_texto`: texto em português que virou embedding e entra no prompt
- `embedding`: vetor de 1536 dims (Matryoshka-truncado, ver ADR em
  `docs/RAG_DESIGN.md`)
- `metadados`: campos estruturados para filtro/exibição no frontend
- `hash_conteudo`: SHA-256 que permite pular re-embed quando nada mudou
- `chave_unica`: chave natural determinística, base do upsert

O registro de origem (quando existe) é referenciado por `referencia_id`
sem FK física — isso permite reindexar sem dependência circular e acomoda
documentos agregados (resumo_funcao, resumo_pca) que não têm registro único.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FonteDocumento(StrEnum):
    """Discriminador de tipo de documento indexado.

    Mantido como StrEnum para serialização trivial e uso direto em queries.
    """

    CONTRATO = "CONTRATO"
    INDICADOR_FISCAL = "INDICADOR_FISCAL"
    RESUMO_FUNCAO = "RESUMO_FUNCAO"
    RESUMO_PCA = "RESUMO_PCA"
    # Eixo da receita orçamentária — RREO-Anexo 01, agregado por
    # (exercício, bimestre, categoria de receita).
    RESUMO_RECEITA = "RESUMO_RECEITA"
    # Eixo da despesa por natureza econômica/grupo (Pessoal, Custeio,
    # Investimentos, etc.) — RREO-Anexo 01.
    RESUMO_NATUREZA_DESPESA = "RESUMO_NATUREZA_DESPESA"


class DocumentoRag(Base):
    """Documento indexado na base vetorial."""

    __tablename__ = "documentos_rag"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Discriminador e referência lógica ao registro de origem
    fonte: Mapped[str] = mapped_column(String(30), index=True)
    referencia_tipo: Mapped[str] = mapped_column(String(30))
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )

    # Chave natural para upsert determinístico
    chave_unica: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Conteúdo indexável
    titulo: Mapped[str] = mapped_column(String(500))
    conteudo_texto: Mapped[str] = mapped_column(Text)
    metadados: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Embedding + proveniência do modelo
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    modelo_embedding: Mapped[str] = mapped_column(String(100))

    # SHA-256 de `conteudo_texto`; permite pular re-embed idempotente
    hash_conteudo: Mapped[str] = mapped_column(String(64))

    indexado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Índice HNSW em `embedding` é criado fora do model, na migração
        # (pgvector.sqlalchemy ainda não suporta HNSW via Mapped Index).
        Index("ix_doc_rag_fonte", "fonte"),
    )
