"""Rotas para contratos firmados."""

import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.api.schemas import ContratoDetail, ContratoOut, PaginatedResponse
from app.models.contratacoes import Contrato

router = APIRouter(prefix="/contratos", tags=["Contratos"])

CampoOrdenacaoContratos = Literal[
    "numero_contrato",
    "objeto",
    "categoria",
    "valor_inicial",
    "data_fim_vigencia",
]
DirecaoOrdenacao = Literal["asc", "desc"]

CAMPOS_ORDENACAO = {
    "numero_contrato": Contrato.numero_contrato,
    "objeto": Contrato.objeto,
    "categoria": Contrato.categoria,
    "valor_inicial": Contrato.valor_inicial,
    "data_fim_vigencia": Contrato.data_fim_vigencia,
}


@router.get("/", response_model=PaginatedResponse[ContratoOut])
async def listar_contratos(
    fornecedor_id: uuid.UUID | None = Query(None, description="Filtrar por fornecedor"),
    situacao: str | None = Query(None, description="Filtrar por situação"),
    categoria: str | None = Query(None, description="Filtrar por categoria"),
    ano: int | None = Query(None, description="Filtrar por ano"),
    data_inicio: date | None = Query(None, description="Vigência final a partir de"),
    data_fim: date | None = Query(None, description="Vigência final até"),
    busca: str | None = Query(None, description="Buscar no objeto do contrato"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=100),
    ordenar_por: CampoOrdenacaoContratos = Query(
        "data_fim_vigencia",
        description="Coluna usada para ordenação",
    ),
    direcao: DirecaoOrdenacao = Query("asc", description="Direção da ordenação"),
    db: AsyncSession = Depends(get_db),
):
    """Lista contratos com filtros opcionais."""
    query = select(Contrato)
    count_query = select(func.count(Contrato.id))

    filtros = []
    if fornecedor_id:
        filtros.append(Contrato.fornecedor_id == fornecedor_id)
    if situacao:
        filtros.append(Contrato.situacao == situacao)
    if categoria:
        filtros.append(Contrato.categoria == categoria)
    if ano:
        filtros.append(Contrato.ano == ano)
    if data_inicio:
        filtros.append(Contrato.data_fim_vigencia >= data_inicio)
    if data_fim:
        filtros.append(Contrato.data_fim_vigencia <= data_fim)
    if busca:
        filtros.append(Contrato.objeto.ilike(f"%{busca}%"))

    for f in filtros:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    coluna_ordenacao = CAMPOS_ORDENACAO[ordenar_por]
    ordenacao = coluna_ordenacao.desc() if direcao == "desc" else coluna_ordenacao.asc()
    result = await db.execute(
        query.order_by(ordenacao.nullslast()).offset(offset).limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


@router.get("/vencendo", response_model=PaginatedResponse[ContratoOut])
async def contratos_vencendo(
    dias: int = Query(30, ge=1, le=365, description="Contratos vencendo nos próximos N dias"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lista contratos com vencimento nos próximos N dias."""
    hoje = date.today()
    limite = hoje + timedelta(days=dias)

    filtro = (Contrato.data_fim_vigencia >= hoje) & (Contrato.data_fim_vigencia <= limite)

    total = (await db.execute(select(func.count(Contrato.id)).where(filtro))).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        select(Contrato)
        .where(filtro)
        .order_by(Contrato.data_fim_vigencia.asc())
        .offset(offset)
        .limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


@router.get("/{contrato_id}", response_model=ContratoDetail)
async def obter_contrato(
    contrato_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna um contrato com fornecedor e contratação vinculados."""
    result = await db.execute(
        select(Contrato)
        .where(Contrato.id == contrato_id)
        .options(
            selectinload(Contrato.fornecedor),
            selectinload(Contrato.contratacao),
        )
    )
    contrato = result.scalar_one_or_none()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return contrato
