"""Schemas Pydantic para request/response da API."""

import uuid
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

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


# ────────────────────────────────────────
# Orçamento (RREO/RGF) — Fase 4
# ────────────────────────────────────────


class ExecucaoOrcamentariaOut(BaseModel):
    """Uma célula do RREO/RGF em formato longo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercicio: int
    periodo: int | None = None
    periodicidade: str | None = None
    tipo_relatorio: str
    anexo: str
    rotulo: str | None = None
    coluna: str
    cod_conta: str
    conta: str
    valor: float | None = None
    orgao_id: uuid.UUID
    cod_ibge: str
    fonte: str
    ingerido_em: datetime


class ResumoFuncaoOut(BaseModel):
    """Resumo de execução por função (agregado a partir do RREO-Anexo 02)."""

    funcao: str
    dotacao_inicial: float | None = None
    dotacao_atualizada: float | None = None
    empenhado: float | None = None
    liquidado: float | None = None
    saldo: float | None = None


class IndicadorFiscalOut(BaseModel):
    """Indicador fiscal derivado (LRF ou mínimo constitucional)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercicio: int
    periodo: int | None = None
    codigo: str
    descricao: str
    unidade: str
    valor: float | None = None
    limite_legal: float | None = None
    situacao: str
    fonte_relatorio: str
    fonte_exercicio: int | None = None
    fonte_periodo: int | None = None
    calculado_em: datetime


class DadosMunicipioOut(BaseModel):
    """Dados contextuais do município em um exercício."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo_ibge: str
    exercicio: int
    nome_municipio: str | None = None
    uf: str | None = None
    populacao: int | None = None
    pib_corrente: float | None = None
    pib_per_capita: float | None = None
    fonte: str
    ingerido_em: datetime


# ─────────────────────────────────────
# Arrecadação tributária (Município Online)
# ─────────────────────────────────────


class ArrecadacaoOut(BaseModel):
    """Linha agregada de arrecadação por item de receita e fonte de recursos."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    orgao_id: uuid.UUID
    cod_ibge: str
    exercicio: int
    mes: int
    data_emissao: date | None = None
    cod_item_receita: str
    descricao_receita: str
    poder: str | None = None
    categoria: str | None = None
    cod_fonte_recurso: str | None = None
    descricao_fonte_recurso: str | None = None
    valor_previsto: float | None = None
    valor_atualizado: float | None = None
    valor_arrecadado_periodo: float | None = None
    valor_arrecadado_acumulado: float | None = None
    fonte: str
    ingerido_em: datetime


class RecolhimentoDetalheOut(BaseModel):
    """Recolhimento individual (detalhe por banco/data/processo)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    arrecadacao_id: uuid.UUID
    orgao_id: uuid.UUID
    exercicio: int
    mes: int
    data_emissao: date | None = None
    numero_processo: str | None = None
    banco: str
    historico: str | None = None
    valor: float | None = None
    ingerido_em: datetime


class SerieAnualArrecadacaoOut(BaseModel):
    """Ponto da série anual de arrecadação."""

    exercicio: int
    valor: float


class SerieMensalArrecadacaoOut(BaseModel):
    """Ponto da série mensal de arrecadação em um exercício."""

    mes: int
    valor: float


class AgregacaoEspecieOut(BaseModel):
    """Total arrecadado por espécie tributária."""

    especie: str
    valor: float
    pct: float


class TopTributoOut(BaseModel):
    """Top-N item de receita por valor arrecadado."""

    cod_item_receita: str
    descricao_receita: str
    valor: float
    pct: float


class AnoEspecieOut(BaseModel):
    """Célula da matriz ano × espécie."""

    exercicio: int
    especie: str
    valor: float


class AgregacaoBancoOut(BaseModel):
    """Total arrecadado por banco recebedor."""

    banco: str
    valor: float
    pct: float


class ResumoArrecadacaoOut(BaseModel):
    """KPIs de arrecadação de um exercício."""

    exercicio: int
    total_arrecadado: float
    total_previsto: float | None = None
    pct_realizacao: float | None = None
    delta_yoy: float | None = None
    n_tributos: int


# ─────────────────────────────────────
# Chat / RAG
# ─────────────────────────────────────


class ChatRequest(BaseModel):
    """Pergunta enviada ao assistente RAG."""

    pergunta: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Pergunta do gestor em linguagem natural.",
    )


class FonteCitadaOut(BaseModel):
    """Documento citado na resposta, com referência navegável."""

    indice: int
    doc_id: uuid.UUID
    fonte: str
    referencia_tipo: str
    referencia_id: uuid.UUID | None = None
    chave_unica: str
    titulo: str
    metadados: dict = {}
    score: float


class ChatResponse(BaseModel):
    """Resposta do assistente RAG com citações."""

    texto: str
    fontes: list[FonteCitadaOut]
    recusou: bool
    latencia_ms: int
