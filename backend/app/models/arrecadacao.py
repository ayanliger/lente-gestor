"""
Modelos de dados para arrecadação tributária municipal.

Fonte: Portal da Transparência (Município Online). Dois níveis:

- `Arrecadacao`: agregado mensal por código de receita (Tesouro Nacional)
  e fonte de recursos. Uma linha por (orgao, exercicio, mes, cod_item,
  cod_fonte). Replica 1:1 a estrutura que o portal expõe na listagem.

- `RecolhimentoDetalhe`: cada recolhimento individual (drill-down do
  portal), com banco recebedor e data de emissão. Vinculado à linha
  agregada correspondente. Permite agregações por banco sem inflar
  a tabela principal.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.contratacoes import Orgao


class Arrecadacao(Base):
    """
    Arrecadação mensal por item de receita e fonte de recursos.

    Granularidade: (orgao, exercicio, mes, cod_item_receita, cod_fonte_recurso).
    Um mesmo código de receita em um mês pode aparecer N vezes, uma por
    fonte de recursos (ex: educação, saúde, não vinculados).
    """

    __tablename__ = "arrecadacao"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Órgão + código IBGE
    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    orgao: Mapped[Orgao] = relationship()
    cod_ibge: Mapped[str] = mapped_column(String(7), index=True)

    # Período
    exercicio: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)  # 1-12
    data_emissao: Mapped[date | None] = mapped_column(Date)

    # Classificação da receita (taxonomia do Tesouro Nacional)
    cod_item_receita: Mapped[str] = mapped_column(String(20), index=True)
    descricao_receita: Mapped[str] = mapped_column(String(500))
    poder: Mapped[str | None] = mapped_column(String(50))  # Executivo/Legislativo
    categoria: Mapped[str | None] = mapped_column(String(50))  # Obrigatória/Voluntária

    # Fonte de recursos (detalhamento fiscal)
    cod_fonte_recurso: Mapped[str | None] = mapped_column(String(20))
    descricao_fonte_recurso: Mapped[str | None] = mapped_column(String(500))

    # Valores
    valor_previsto: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_atualizado: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_arrecadado_periodo: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    valor_arrecadado_acumulado: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Rastreabilidade
    fonte: Mapped[str] = mapped_column(String(30))  # MUNICIPIO_ONLINE
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    recolhimentos: Mapped[list["RecolhimentoDetalhe"]] = relationship(
        back_populates="arrecadacao",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_arrecadacao_unique",
            "orgao_id",
            "exercicio",
            "mes",
            "cod_item_receita",
            "cod_fonte_recurso",
            unique=True,
        ),
        Index("ix_arrecadacao_exerc_mes", "exercicio", "mes"),
    )


class RecolhimentoDetalhe(Base):
    """
    Recolhimento individual (drill-down do portal).

    Representa um evento de arrecadação identificado pelo portal com
    data de emissão, processo, banco recebedor, valor e histórico.
    Vinculado à linha agregada correspondente em `arrecadacao`.
    """

    __tablename__ = "recolhimento_detalhe"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    arrecadacao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("arrecadacao.id", ondelete="CASCADE"), index=True
    )
    arrecadacao: Mapped[Arrecadacao] = relationship(back_populates="recolhimentos")

    # Denormalizado para `GROUP BY banco` sem join com arrecadacao.
    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    exercicio: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)

    # Dados do recolhimento
    data_emissao: Mapped[date | None] = mapped_column(Date)
    numero_processo: Mapped[str | None] = mapped_column(String(100))
    banco: Mapped[str] = mapped_column(String(255), index=True)
    historico: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Rastreabilidade
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Chave natural: portal não expõe ID estável por recolhimento.
        # A combinação desses 5 campos é suficiente para detectar duplicatas
        # em re-ingestão do mesmo mês.
        Index(
            "ix_recolhimento_unique",
            "arrecadacao_id",
            "numero_processo",
            "banco",
            "data_emissao",
            "valor",
            unique=True,
        ),
    )
