"""Rotas para dados contextuais do município (IBGE)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import DadosMunicipioOut
from app.models.orcamento import DadosMunicipio

router = APIRouter(prefix="/municipio", tags=["Município"])


@router.get("/dados", response_model=list[DadosMunicipioOut])
async def listar_dados_municipio(
    exercicio: int | None = Query(None, description="Se informado, retorna só o ano"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna dados contextuais (população, PIB, PIB per capita) do município.

    Sem filtro → série histórica completa.
    Com `exercicio` → apenas aquele ano.
    """
    query = select(DadosMunicipio).order_by(DadosMunicipio.exercicio.desc())
    if exercicio is not None:
        query = query.where(DadosMunicipio.exercicio == exercicio)

    result = await db.execute(query)
    return result.scalars().all()
