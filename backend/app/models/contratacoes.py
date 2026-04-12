"""
Modelos de dados para contratações e contratos.

Baseado nos dados retornados pela API do PNCP e fontes complementares.
Os campos serão refinados conforme a estrutura real dos dados ingeridos.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Orgao(Base):
    """Órgão/entidade contratante."""

    __tablename__ = "orgaos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    razao_social: Mapped[str] = mapped_column(String(255))
    esfera: Mapped[str | None] = mapped_column(String(50))
    uf: Mapped[str | None] = mapped_column(String(2))
    municipio: Mapped[str | None] = mapped_column(String(255))

    contratacoes: Mapped[list["Contratacao"]] = relationship(back_populates="orgao")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Fornecedor(Base):
    """Fornecedor / empresa contratada."""

    __tablename__ = "fornecedores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpf_cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str | None] = mapped_column(String(20))  # PF / PJ

    contratos: Mapped[list["Contrato"]] = relationship(back_populates="fornecedor")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Contratacao(Base):
    """
    Processo de contratação (licitação, dispensa, inexigibilidade).

    Corresponde a um registro no endpoint /contratacoes/publicacao do PNCP.
    """

    __tablename__ = "contratacoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificação PNCP
    pncp_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    numero_sequencial: Mapped[int | None] = mapped_column()
    ano: Mapped[int | None] = mapped_column()
    numero_processo: Mapped[str | None] = mapped_column(String(100))

    # Órgão
    orgao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orgaos.id"))
    orgao: Mapped[Orgao | None] = relationship(back_populates="contratacoes")

    # Dados da contratação
    modalidade: Mapped[str | None] = mapped_column(String(100))
    tipo: Mapped[str | None] = mapped_column(String(100))  # Compra, Serviço, Obra
    objeto: Mapped[str | None] = mapped_column(Text)
    valor_estimado: Mapped[float | None] = mapped_column(Numeric(15, 2))
    valor_homologado: Mapped[float | None] = mapped_column(Numeric(15, 2))
    situacao: Mapped[str | None] = mapped_column(String(50))

    # Datas
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    data_abertura: Mapped[date | None] = mapped_column(Date)
    data_homologacao: Mapped[date | None] = mapped_column(Date)

    # Metadados de ingestão
    fonte: Mapped[str] = mapped_column(String(20), default="pncp")
    dados_brutos: Mapped[str | None] = mapped_column(Text)  # JSON original para referência
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    contratos: Mapped[list["Contrato"]] = relationship(back_populates="contratacao")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_contratacoes_orgao_ano", "orgao_id", "ano"),
        Index("ix_contratacoes_modalidade", "modalidade"),
    )


class Contrato(Base):
    """
    Contrato firmado.

    Pode estar vinculado a uma contratação (licitação) ou ser direto.
    """

    __tablename__ = "contratos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificação
    pncp_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    numero_contrato: Mapped[str | None] = mapped_column(String(100))
    ano: Mapped[int | None] = mapped_column()

    # Vínculos
    contratacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratacoes.id"))
    contratacao: Mapped[Contratacao | None] = relationship(back_populates="contratos")
    fornecedor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fornecedores.id"))
    fornecedor: Mapped[Fornecedor | None] = relationship(back_populates="contratos")

    # Dados do contrato
    objeto: Mapped[str | None] = mapped_column(Text)
    valor_inicial: Mapped[float | None] = mapped_column(Numeric(15, 2))
    valor_atual: Mapped[float | None] = mapped_column(Numeric(15, 2))  # Após aditivos
    valor_aditivos: Mapped[float | None] = mapped_column(Numeric(15, 2))

    # Vigência
    data_assinatura: Mapped[date | None] = mapped_column(Date)
    data_inicio_vigencia: Mapped[date | None] = mapped_column(Date)
    data_fim_vigencia: Mapped[date | None] = mapped_column(Date, index=True)
    situacao: Mapped[str | None] = mapped_column(String(50))

    # Categoria
    categoria: Mapped[str | None] = mapped_column(String(100))
    subcategoria: Mapped[str | None] = mapped_column(String(100))

    # Metadados de ingestão
    fonte: Mapped[str] = mapped_column(String(20), default="pncp")
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_contratos_fornecedor", "fornecedor_id"),
        Index("ix_contratos_vigencia", "data_fim_vigencia"),
    )


class ItemPCA(Base):
    """
    Item do Plano de Contratações Anual (PCA).

    Permite cruzar o que foi planejado com o que foi efetivamente contratado.
    """

    __tablename__ = "itens_pca"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificação
    pncp_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    ano_exercicio: Mapped[int] = mapped_column(index=True)

    # Dados do item
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria: Mapped[str | None] = mapped_column(String(100))
    valor_estimado: Mapped[float | None] = mapped_column(Numeric(15, 2))
    valor_executado: Mapped[float | None] = mapped_column(Numeric(15, 2))  # Calculado
    unidade_requisitante: Mapped[str | None] = mapped_column(String(255))
    data_prevista: Mapped[date | None] = mapped_column(Date)
    situacao: Mapped[str | None] = mapped_column(String(50))

    # Metadados
    fonte: Mapped[str] = mapped_column(String(20), default="pncp")
    dados_brutos: Mapped[str | None] = mapped_column(Text)
    ingerido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
