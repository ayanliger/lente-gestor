"""Rotas para dados orçamentários (RREO/RGF + indicadores fiscais)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import (
    ExecucaoOrcamentariaOut,
    IndicadorFiscalOut,
    PaginatedResponse,
    ResumoFuncaoOut,
)
from app.models.orcamento import ExecucaoOrcamentaria, IndicadorFiscal

router = APIRouter(prefix="/orcamento", tags=["Orçamento"])


# ──────────────────────────────────────────
# Execução orçamentária (células brutas)
# ──────────────────────────────────────────


@router.get("/execucao", response_model=PaginatedResponse[ExecucaoOrcamentariaOut])
async def listar_execucao(
    exercicio: int | None = Query(None),
    periodo: int | None = Query(None),
    tipo_relatorio: str | None = Query(None, description="RREO ou RGF"),
    anexo: str | None = Query(None),
    cod_conta: str | None = Query(None),
    coluna: str | None = Query(None),
    busca: str | None = Query(None, description="Buscar em conta/rotulo (ILIKE)"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Lista células do RREO/RGF com filtros e paginação."""
    query = select(ExecucaoOrcamentaria)
    count_query = select(func.count(ExecucaoOrcamentaria.id))

    filtros = []
    if exercicio is not None:
        filtros.append(ExecucaoOrcamentaria.exercicio == exercicio)
    if periodo is not None:
        filtros.append(ExecucaoOrcamentaria.periodo == periodo)
    if tipo_relatorio:
        filtros.append(ExecucaoOrcamentaria.tipo_relatorio == tipo_relatorio)
    if anexo:
        filtros.append(ExecucaoOrcamentaria.anexo == anexo)
    if cod_conta:
        filtros.append(ExecucaoOrcamentaria.cod_conta == cod_conta)
    if coluna:
        filtros.append(ExecucaoOrcamentaria.coluna == coluna)
    if busca:
        like = f"%{busca}%"
        filtros.append(
            ExecucaoOrcamentaria.conta.ilike(like)
            | ExecucaoOrcamentaria.rotulo.ilike(like)
        )

    for f in filtros:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        query.order_by(
            ExecucaoOrcamentaria.exercicio.desc(),
            ExecucaoOrcamentaria.periodo.desc().nullslast(),
            ExecucaoOrcamentaria.anexo,
            ExecucaoOrcamentaria.cod_conta,
        )
        .offset(offset)
        .limit(tamanho_pagina)
    )

    return PaginatedResponse(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        dados=result.scalars().all(),
    )


# ──────────────────────────────────────────
# Resumo por função (RREO-Anexo 02 pivoteado)
# ──────────────────────────────────────────


# Rótulo e colunas do RREO-Anexo 02 que representam execução por função.
_ROTULO_FUNCOES = "Total das Despesas Exceto Intra-Orçamentárias"
_COL_DOT_INICIAL = "DOTAÇÃO INICIAL"
_COL_DOT_ATUALIZADA = "DOTAÇÃO ATUALIZADA (a)"
_COL_EMPENHADO = "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)"
_COL_LIQUIDADO = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)"
_COL_SALDO = "SALDO (c) = (a-b)"


@router.get("/resumo-por-funcao", response_model=list[ResumoFuncaoOut])
async def resumo_por_funcao(
    exercicio: int = Query(..., description="Ano do exercício"),
    periodo: int | None = Query(None, description="Bimestre; omitir usa o mais recente"),
    limite: int = Query(50, ge=1, le=200, description="Máximo de funções a retornar"),
    db: AsyncSession = Depends(get_db),
):
    """
    Agrega execução por função (RREO-Anexo 02) com pivot nas principais
    colunas: dotação inicial/atualizada, empenhado, liquidado, saldo.

    Ordena por valor empenhado descendente. Exclui linhas-totalizadoras.
    """
    # Descobrir período mais recente se não informado
    if periodo is None:
        res = await db.execute(
            select(func.max(ExecucaoOrcamentaria.periodo)).where(
                ExecucaoOrcamentaria.exercicio == exercicio,
                ExecucaoOrcamentaria.tipo_relatorio == "RREO",
                ExecucaoOrcamentaria.anexo == "RREO-Anexo 02",
            )
        )
        periodo = res.scalar_one_or_none()
        if periodo is None:
            return []

    def pivot_col(nome_col: str):
        return func.max(
            case((ExecucaoOrcamentaria.coluna == nome_col, ExecucaoOrcamentaria.valor))
        )

    query = (
        select(
            ExecucaoOrcamentaria.conta.label("funcao"),
            pivot_col(_COL_DOT_INICIAL).label("dotacao_inicial"),
            pivot_col(_COL_DOT_ATUALIZADA).label("dotacao_atualizada"),
            pivot_col(_COL_EMPENHADO).label("empenhado"),
            pivot_col(_COL_LIQUIDADO).label("liquidado"),
            pivot_col(_COL_SALDO).label("saldo"),
        )
        .where(
            ExecucaoOrcamentaria.exercicio == exercicio,
            ExecucaoOrcamentaria.periodo == periodo,
            ExecucaoOrcamentaria.tipo_relatorio == "RREO",
            ExecucaoOrcamentaria.anexo == "RREO-Anexo 02",
            ExecucaoOrcamentaria.rotulo == _ROTULO_FUNCOES,
            # Excluir linhas-totalizadoras conhecidas
            ExecucaoOrcamentaria.conta.notilike("DESPESAS%"),
            ExecucaoOrcamentaria.conta != "TOTAL (III) = (I + II)",
        )
        .group_by(ExecucaoOrcamentaria.conta)
        .order_by(pivot_col(_COL_EMPENHADO).desc().nullslast())
        .limit(limite)
    )

    result = await db.execute(query)
    rows = result.all()
    return [
        ResumoFuncaoOut(
            funcao=r.funcao,
            dotacao_inicial=float(r.dotacao_inicial) if r.dotacao_inicial is not None else None,
            dotacao_atualizada=float(r.dotacao_atualizada) if r.dotacao_atualizada is not None else None,
            empenhado=float(r.empenhado) if r.empenhado is not None else None,
            liquidado=float(r.liquidado) if r.liquidado is not None else None,
            saldo=float(r.saldo) if r.saldo is not None else None,
        )
        for r in rows
    ]


# ──────────────────────────────────────────
# Indicadores fiscais
# ──────────────────────────────────────────


@router.get("/indicadores", response_model=list[IndicadorFiscalOut])
async def listar_indicadores(
    exercicio: int | None = Query(None),
    periodo: int | None = Query(None),
    codigo: str | None = Query(None),
    situacao: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Lista indicadores fiscais derivados (LRF + mínimos constitucionais)."""
    query = select(IndicadorFiscal)
    if exercicio is not None:
        query = query.where(IndicadorFiscal.exercicio == exercicio)
    if periodo is not None:
        query = query.where(IndicadorFiscal.periodo == periodo)
    if codigo:
        query = query.where(IndicadorFiscal.codigo == codigo)
    if situacao:
        query = query.where(IndicadorFiscal.situacao == situacao)

    result = await db.execute(
        query.order_by(IndicadorFiscal.exercicio.desc(), IndicadorFiscal.codigo)
    )
    return result.scalars().all()
