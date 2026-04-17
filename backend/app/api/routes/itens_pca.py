"""Rotas para itens do Plano de Contratações Anual (PCA)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import ItemPCAOut, PaginatedResponse
from app.models.contratacoes import ItemPCA

router = APIRouter(prefix="/pca", tags=["PCA"])


@router.get("/", response_model=PaginatedResponse[ItemPCAOut])
async def listar_itens_pca(
    ano_exercicio: int | None = Query(None, description="Filtrar por ano de exercício"),
    categoria: str | None = Query(None, description="Filtrar por categoria"),
    situacao: str | None = Query(None, description="Filtrar por situação"),
    busca: str | None = Query(None, description="Buscar na descrição do item"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lista itens do PCA com filtros opcionais."""
    query = select(ItemPCA)
    count_query = select(func.count(ItemPCA.id))

    filtros = []
    if ano_exercicio:
        filtros.append(ItemPCA.ano_exercicio == ano_exercicio)
    if categoria:
        filtros.append(ItemPCA.categoria == categoria)
    if situacao:
        filtros.append(ItemPCA.situacao == situacao)
    if busca:
        filtros.append(ItemPCA.descricao.ilike(f"%{busca}%"))

    for f in filtros:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        query.order_by(ItemPCA.ano_exercicio.desc(), ItemPCA.data_prevista.asc().nullslast())
        .offset(offset)
        .limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


@router.get("/{item_id}", response_model=ItemPCAOut)
async def obter_item_pca(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna um item do PCA pelo ID."""
    item = await db.get(ItemPCA, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item PCA não encontrado")
    return item
