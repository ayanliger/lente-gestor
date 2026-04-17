"""Schemas Pydantic para request/response da API."""

import uuid
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


# ──────────────────────────────────────────
# Paginação
# ──────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    """Resposta paginada genérica."""

    total: int
    pagina: int
    tamanho_pagina: int
    dados: list[T]


# ──────────────────────────────────────────
# Órgãos
# ──────────────────────────────────────────


class OrgaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnpj: str
    razao_social: str
    esfera: str | None = None
    uf: str | None = None
    municipio: str | None = None
    created_at: datetime


# ──────────────────────────────────────────
# Fornecedores
# ──────────────────────────────────────────


class FornecedorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cpf_cnpj: str
    nome: str
    tipo: str | None = None
    created_at: datetime


# ──────────────────────────────────────────
# Contratações
# ──────────────────────────────────────────


class ContratacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pncp_id: str | None = None
    numero_sequencial: int | None = None
    ano: int | None = None
    numero_processo: str | None = None
    orgao_id: uuid.UUID | None = None
    modalidade: str | None = None
    tipo: str | None = None
    objeto: str | None = None
    valor_estimado: float | None = None
    valor_homologado: float | None = None
    situacao: str | None = None
    data_publicacao: date | None = None
    data_abertura: date | None = None
    data_homologacao: date | None = None
    fonte: str
    ingerido_em: datetime
    created_at: datetime


class ContratacaoDetail(ContratacaoOut):
    """Contratação com dados completos e contratos vinculados."""

    dados_brutos: str | None = None
    contratos: list["ContratoOut"] = []


# ──────────────────────────────────────────
# Contratos
# ──────────────────────────────────────────


class ContratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pncp_id: str | None = None
    numero_contrato: str | None = None
    ano: int | None = None
    contratacao_id: uuid.UUID | None = None
    fornecedor_id: uuid.UUID | None = None
    objeto: str | None = None
    valor_inicial: float | None = None
    valor_atual: float | None = None
    valor_aditivos: float | None = None
    data_assinatura: date | None = None
    data_inicio_vigencia: date | None = None
    data_fim_vigencia: date | None = None
    situacao: str | None = None
    categoria: str | None = None
    subcategoria: str | None = None
    fonte: str
    ingerido_em: datetime
    created_at: datetime


class ContratoDetail(ContratoOut):
    """Contrato com dados completos e entidades relacionadas."""

    dados_brutos: str | None = None
    fornecedor: FornecedorOut | None = None
    contratacao: ContratacaoOut | None = None


# ──────────────────────────────────────────
# Itens PCA
# ──────────────────────────────────────────


class ItemPCAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pncp_id: str | None = None
    ano_exercicio: int
    descricao: str | None = None
    categoria: str | None = None
    valor_estimado: float | None = None
    valor_executado: float | None = None
    unidade_requisitante: str | None = None
    data_prevista: date | None = None
    situacao: str | None = None
    fonte: str
    ingerido_em: datetime
    created_at: datetime


# Resolver forward reference
ContratacaoDetail.model_rebuild()
