"""Rotas para contratações (licitações, dispensas, inexigibilidades)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.api.schemas import ContratacaoDetail, ContratacaoOut, PaginatedResponse
from app.models.contratacoes import Contratacao

router = APIRouter(prefix="/contratacoes", tags=["Contratações"])


@router.get("/", response_model=PaginatedResponse[ContratacaoOut])
async def listar_contratacoes(
    ano: int | None = Query(None, description="Filtrar por ano"),
    modalidade: str | None = Query(None, description="Filtrar por modalidade"),
    situacao: str | None = Query(None, description="Filtrar por situação"),
    orgao_id: uuid.UUID | None = Query(None, description="Filtrar por órgão"),
    data_inicio: date | None = Query(None, description="Data de publicação inicial"),
    data_fim: date | None = Query(None, description="Data de publicação final"),
    busca: str | None = Query(None, description="Buscar no objeto da contratação"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lista contratações com filtros opcionais."""
    query = select(Contratacao)
    count_query = select(func.count(Contratacao.id))

    filtros = []
    if ano:
        filtros.append(Contratacao.ano == ano)
    if modalidade:
        filtros.append(Contratacao.modalidade == modalidade)
    if situacao:
        filtros.append(Contratacao.situacao == situacao)
    if orgao_id:
        filtros.append(Contratacao.orgao_id == orgao_id)
    if data_inicio:
        filtros.append(Contratacao.data_publicacao >= data_inicio)
    if data_fim:
        filtros.append(Contratacao.data_publicacao <= data_fim)
    if busca:
        filtros.append(Contratacao.objeto.ilike(f"%{busca}%"))

    for f in filtros:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        query.order_by(Contratacao.data_publicacao.desc().nullslast())
        .offset(offset)
        .limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


@router.get("/{contratacao_id}", response_model=ContratacaoDetail)
async def obter_contratacao(
    contratacao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna uma contratação com seus contratos vinculados."""
    result = await db.execute(
        select(Contratacao)
        .where(Contratacao.id == contratacao_id)
        .options(selectinload(Contratacao.contratos))
    )
    contratacao = result.scalar_one_or_none()
    if not contratacao:
        raise HTTPException(status_code=404, detail="Contratação não encontrada")
    return contratacao
