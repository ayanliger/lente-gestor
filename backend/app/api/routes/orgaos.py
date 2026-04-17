"""Rotas para órgãos/entidades contratantes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import OrgaoOut, PaginatedResponse
from app.models.contratacoes import Orgao

router = APIRouter(prefix="/orgaos", tags=["Órgãos"])


@router.get("/", response_model=PaginatedResponse[OrgaoOut])
async def listar_orgaos(
    busca: str | None = Query(None, description="Buscar por razão social ou CNPJ"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lista órgãos com busca opcional."""
    query = select(Orgao)
    count_query = select(func.count(Orgao.id))

    if busca:
        filtro = Orgao.razao_social.ilike(f"%{busca}%") | Orgao.cnpj.contains(busca)
        query = query.where(filtro)
        count_query = count_query.where(filtro)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        query.order_by(Orgao.razao_social).offset(offset).limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


@router.get("/{orgao_id}", response_model=OrgaoOut)
async def obter_orgao(
    orgao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna um órgão pelo ID."""
    orgao = await db.get(Orgao, orgao_id)
    if not orgao:
        raise HTTPException(status_code=404, detail="Órgão não encontrado")
    return orgao
