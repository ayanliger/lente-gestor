"""rag: documentos_rag + índice HNSW (pgvector)

Revision ID: a1f7e0b2c3d4
Revises: 3710dc007ebc
Create Date: 2026-04-18 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "a1f7e0b2c3d4"
down_revision: str | None = "3710dc007ebc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Garante que a extensão pgvector esteja disponível (idempotente).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documentos_rag",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("fonte", sa.String(length=30), nullable=False),
        sa.Column("referencia_tipo", sa.String(length=30), nullable=False),
        sa.Column("referencia_id", sa.UUID(), nullable=True),
        sa.Column("chave_unica", sa.String(length=255), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("conteudo_texto", sa.Text(), nullable=False),
        sa.Column(
            "metadados",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("modelo_embedding", sa.String(length=100), nullable=False),
        sa.Column("hash_conteudo", sa.String(length=64), nullable=False),
        sa.Column(
            "indexado_em",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chave_unica", name="uq_doc_rag_chave_unica"),
    )

    op.create_index("ix_doc_rag_fonte", "documentos_rag", ["fonte"], unique=False)
    op.create_index(
        op.f("ix_documentos_rag_referencia_id"),
        "documentos_rag",
        ["referencia_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documentos_rag_chave_unica"),
        "documentos_rag",
        ["chave_unica"],
        unique=True,
    )

    # Índice HNSW com ops de cosseno; usa defaults do pgvector (m=16, ef_construction=64).
    # Com 1536 dims o HNSW cabe dentro do limite nativo do pgvector (2000).
    op.execute(
        "CREATE INDEX ix_doc_rag_embedding_hnsw "
        "ON documentos_rag USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_doc_rag_embedding_hnsw")
    op.drop_index(op.f("ix_documentos_rag_chave_unica"), table_name="documentos_rag")
    op.drop_index(op.f("ix_documentos_rag_referencia_id"), table_name="documentos_rag")
    op.drop_index("ix_doc_rag_fonte", table_name="documentos_rag")
    op.drop_table("documentos_rag")
    # A extensão `vector` não é removida — compartilhada com outros esquemas.
