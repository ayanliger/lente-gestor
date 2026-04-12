"""Rotas para fornecedores / empresas contratadas."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import FornecedorOut, PaginatedResponse
from app.models.contratacoes import Fornecedor

router = APIRouter(prefix="/fornecedores", tags=["Fornecedores"])


@router.get("/", response_model=PaginatedResponse[FornecedorOut])
async def listar_fornecedores(
    busca: str | None = Query(None, description="Buscar por nome ou CPF/CNPJ"),
    tipo: str | None = Query(None, description="Filtrar por tipo (PF / PJ)"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lista fornecedores com busca e filtros opcionais."""
    query = select(Fornecedor)
    count_query = select(func.count(Fornecedor.id))

    if busca:
        filtro = Fornecedor.nome.ilike(f"%{busca}%") | Fornecedor.cpf_cnpj.contains(busca)
        query = query.where(filtro)
        count_query = count_query.where(filtro)

    if tipo:
        query = query.where(Fornecedor.tipo == tipo)
        count_query = count_query.where(Fornecedor.tipo == tipo)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        query.order_by(Fornecedor.nome).offset(offset).limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


@router.get("/{fornecedor_id}", response_model=FornecedorOut)
async def obter_fornecedor(
    fornecedor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna um fornecedor pelo ID."""
    fornecedor = await db.get(Fornecedor, fornecedor_id)
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    return fornecedor
