"""arrecadacao: agregado mensal + recolhimento_detalhe (Município Online)

Revision ID: c2e91a4f7d38
Revises: a1f7e0b2c3d4
Create Date: 2026-04-21 19:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2e91a4f7d38"
down_revision: Union[str, None] = "a1f7e0b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "arrecadacao",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("orgao_id", sa.UUID(), nullable=False),
        sa.Column("cod_ibge", sa.String(length=7), nullable=False),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("cod_item_receita", sa.String(length=20), nullable=False),
        sa.Column("descricao_receita", sa.String(length=500), nullable=False),
        sa.Column("poder", sa.String(length=50), nullable=True),
        sa.Column("categoria", sa.String(length=50), nullable=True),
        sa.Column("cod_fonte_recurso", sa.String(length=20), nullable=True),
        sa.Column("descricao_fonte_recurso", sa.String(length=500), nullable=True),
        sa.Column("valor_previsto", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("valor_atualizado", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column(
            "valor_arrecadado_periodo", sa.Numeric(precision=18, scale=2), nullable=True
        ),
        sa.Column(
            "valor_arrecadado_acumulado",
            sa.Numeric(precision=18, scale=2),
            nullable=True,
        ),
        sa.Column("fonte", sa.String(length=30), nullable=False),
        sa.Column("dados_brutos", sa.Text(), nullable=True),
        sa.Column(
            "ingerido_em",
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
        sa.ForeignKeyConstraint(["orgao_id"], ["orgaos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_arrecadacao_unique",
        "arrecadacao",
        [
            "orgao_id",
            "exercicio",
            "mes",
            "cod_item_receita",
            "cod_fonte_recurso",
        ],
        unique=True,
    )
    op.create_index(
        "ix_arrecadacao_exerc_mes", "arrecadacao", ["exercicio", "mes"], unique=False
    )
    op.create_index(
        op.f("ix_arrecadacao_orgao_id"), "arrecadacao", ["orgao_id"], unique=False
    )
    op.create_index(
        op.f("ix_arrecadacao_cod_ibge"), "arrecadacao", ["cod_ibge"], unique=False
    )
    op.create_index(
        op.f("ix_arrecadacao_exercicio"), "arrecadacao", ["exercicio"], unique=False
    )
    op.create_index(op.f("ix_arrecadacao_mes"), "arrecadacao", ["mes"], unique=False)
    op.create_index(
        op.f("ix_arrecadacao_cod_item_receita"),
        "arrecadacao",
        ["cod_item_receita"],
        unique=False,
    )

    op.create_table(
        "recolhimento_detalhe",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("arrecadacao_id", sa.UUID(), nullable=False),
        sa.Column("orgao_id", sa.UUID(), nullable=False),
        sa.Column("exercicio", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("numero_processo", sa.String(length=100), nullable=True),
        sa.Column("banco", sa.String(length=255), nullable=False),
        sa.Column("historico", sa.Text(), nullable=True),
        sa.Column("valor", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("dados_brutos", sa.Text(), nullable=True),
        sa.Column(
            "ingerido_em",
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
        sa.ForeignKeyConstraint(
            ["arrecadacao_id"], ["arrecadacao.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["orgao_id"], ["orgaos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recolhimento_unique",
        "recolhimento_detalhe",
        ["arrecadacao_id", "numero_processo", "banco", "data_emissao", "valor"],
        unique=True,
    )
    op.create_index(
        op.f("ix_recolhimento_detalhe_arrecadacao_id"),
        "recolhimento_detalhe",
        ["arrecadacao_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recolhimento_detalhe_orgao_id"),
        "recolhimento_detalhe",
        ["orgao_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recolhimento_detalhe_banco"),
        "recolhimento_detalhe",
        ["banco"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recolhimento_detalhe_exercicio"),
        "recolhimento_detalhe",
        ["exercicio"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recolhimento_detalhe_mes"),
        "recolhimento_detalhe",
        ["mes"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_recolhimento_detalhe_mes"), table_name="recolhimento_detalhe"
    )
    op.drop_index(
        op.f("ix_recolhimento_detalhe_exercicio"), table_name="recolhimento_detalhe"
    )
    op.drop_index(
        op.f("ix_recolhimento_detalhe_banco"), table_name="recolhimento_detalhe"
    )
    op.drop_index(
        op.f("ix_recolhimento_detalhe_orgao_id"), table_name="recolhimento_detalhe"
    )
    op.drop_index(
        op.f("ix_recolhimento_detalhe_arrecadacao_id"),
        table_name="recolhimento_detalhe",
    )
    op.drop_index("ix_recolhimento_unique", table_name="recolhimento_detalhe")
    op.drop_table("recolhimento_detalhe")

    op.drop_index(op.f("ix_arrecadacao_cod_item_receita"), table_name="arrecadacao")
    op.drop_index(op.f("ix_arrecadacao_mes"), table_name="arrecadacao")
    op.drop_index(op.f("ix_arrecadacao_exercicio"), table_name="arrecadacao")
    op.drop_index(op.f("ix_arrecadacao_cod_ibge"), table_name="arrecadacao")
    op.drop_index(op.f("ix_arrecadacao_orgao_id"), table_name="arrecadacao")
    op.drop_index("ix_arrecadacao_exerc_mes", table_name="arrecadacao")
    op.drop_index("ix_arrecadacao_unique", table_name="arrecadacao")
    op.drop_table("arrecadacao")
