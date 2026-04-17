"""
Modelos de dados para execução orçamentária e indicadores fiscais.

Baseado nos relatórios do SICONFI (Tesouro Nacional). A tabela
`execucao_orcamentaria` armazena cada célula dos relatórios RREO/DCA
em formato longo — uma linha por (anexo, coluna, conta), refletindo
1:1 a resposta da API (ADR 10.2).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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


class ExecucaoOrcamentaria(Base):
    """
    Uma célula do relatório RREO/DCA do SICONFI.

    Formato longo: um registro representa (anexo × coluna × conta)
    em um (exercício, período) de um ente federativo.
    """

    __tablename__ = "execucao_orcamentaria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Período / tipo de relatório
    exercicio: Mapped[int] = mapped_column(Integer, index=True)
    periodo: Mapped[int | None] = mapped_column(Integer, index=True)  # bimestre 1-6
    periodicidade: Mapped[str | None] = mapped_column(String(5))  # B, Q, A
    tipo_relatorio: Mapped[str] = mapped_column(String(10), index=True)  # RREO, DCA

    # Classificação SICONFI (long format)
    anexo: Mapped[str] = mapped_column(String(100), index=True)
    rotulo: Mapped[str | None] = mapped_column(String(255))
    coluna: Mapped[str] = mapped_column(String(255), index=True)
    cod_conta: Mapped[str] = mapped_column(String(255), index=True)
    # conta é discriminador: um único cod_conta pode ter N contas
    # (ex: funções/subfunções diferentes no mesmo agrupamento).
    conta: Mapped[str] = mapped_column(String(500))

    # Valor da célula
    valor: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Órgão + código IBGE
    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    orgao: Mapped[Orgao] = relationship()
    cod_ibge: Mapped[str] = mapped_column(String(7), index=True)

    # Rastreabilidade
    fonte: Mapped[str] = mapped_column(String(20))  # SICONFI_RREO, SICONFI_DCA
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_exec_orc_unique",
            "orgao_id",
            "exercicio",
            "periodo",
            "tipo_relatorio",
            "anexo",
            "cod_conta",
            "coluna",
            "conta",
            unique=True,
        ),
        Index("ix_exec_orc_exerc_anexo", "exercicio", "anexo"),
    )


class DadosMunicipio(Base):
    """
    Dados contextuais (população, PIB) do município em um exercício.

    Fonte principal: IBGE (SIDRA) + metadados de `/v1/localidades/municipios`.
    Uma linha por (orgao, exercício) — permite séries históricas e
    cálculos per capita cruzando com `execucao_orcamentaria`.
    """

    __tablename__ = "dados_municipio"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    orgao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgaos.id"), index=True)
    orgao: Mapped[Orgao] = relationship()
    codigo_ibge: Mapped[str] = mapped_column(String(7), index=True)

    exercicio: Mapped[int] = mapped_column(Integer, index=True)

    # Metadados do município
    nome_municipio: Mapped[str | None] = mapped_column(String(255))
    uf: Mapped[str | None] = mapped_column(String(2))

    # Dados socioeconômicos
    populacao: Mapped[int | None] = mapped_column(Integer)
    pib_corrente: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    pib_per_capita: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # Rastreabilidade
    fonte: Mapped[str] = mapped_column(String(20))  # IBGE
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_dados_mun_unique", "orgao_id", "exercicio", unique=True),
    )
