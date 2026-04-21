"""Rotas para dados de arrecadação tributária (Município Online)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import (
    AgregacaoBancoOut,
    AgregacaoEspecieOut,
    AnoEspecieOut,
    ArrecadacaoOut,
    MesAnoArrecadacaoOut,
    PaginatedResponse,
    PorReceitaContabilOut,
    ResumoArrecadacaoOut,
    SerieAnualArrecadacaoOut,
    SerieMensalArrecadacaoOut,
    TopTributoOut,
)
from app.models.arrecadacao import Arrecadacao, RecolhimentoDetalhe

router = APIRouter(prefix="/arrecadacao", tags=["Arrecadação"])


# ─────────────────────────────────────
# Derivação de espécie tributária (taxonomia Tesouro Nacional)
# ─────────────────────────────────────


def _especie_case():
    """
    Retorna a expressão SQL que mapeia cod_item_receita → espécie tributária.

    Usa CASE em SQL para manter a classificação em um único lugar.
    Prefixos são da taxonomia de Natureza da Receita do STN.
    """
    return case(
        (Arrecadacao.cod_item_receita.like("111%"), "Impostos"),
        (Arrecadacao.cod_item_receita.like("112%"), "Taxas"),
        (Arrecadacao.cod_item_receita.like("113%"), "Contribuição de Melhoria"),
        (Arrecadacao.cod_item_receita.like("12%"), "Contribuições"),
        (Arrecadacao.cod_item_receita.like("13%"), "Patrimonial"),
        (Arrecadacao.cod_item_receita.like("14%"), "Agropecuária"),
        (Arrecadacao.cod_item_receita.like("15%"), "Industrial"),
        (Arrecadacao.cod_item_receita.like("16%"), "Serviços"),
        (Arrecadacao.cod_item_receita.like("17%"), "Transferências"),
        (Arrecadacao.cod_item_receita.like("19%"), "Não Tributária"),
        (Arrecadacao.cod_item_receita.like("2%"), "Capital"),
        (Arrecadacao.cod_item_receita.like("7%"), "Intraorçamentária"),
        (Arrecadacao.cod_item_receita.like("8%"), "Intraorçamentária"),
        else_="Outras",
    )


# O portal expõe arrecadação sempre detalhada por fonte de recursos;
# a soma das fontes de um item corresponde ao total do item (não há
# linha "total" separada). Por isso as agregações somam todas as linhas
# diretamente. O parser emite `cod_fonte_recurso=None` apenas como
# fallback quando o portal excepcionalmente não traz fontes — essa
# linha, se existir, já representa o total do item, então somar todas
# continua correto (o parser nunca emite "total" + "fontes" para o
# mesmo item no mesmo mês).


# ──────────────────────────────────────────
# Listagem paginada
# ──────────────────────────────────────────


@router.get("/", response_model=PaginatedResponse[ArrecadacaoOut])
async def listar_arrecadacao(
    exercicio: int | None = Query(None),
    mes: int | None = Query(None, ge=1, le=12),
    cod_item_receita: str | None = Query(None),
    busca: str | None = Query(None, description="ILIKE em descricao_receita"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Lista registros de arrecadação agregada com filtros e paginação."""
    query = select(Arrecadacao)
    count_query = select(func.count(Arrecadacao.id))

    filtros = []
    if exercicio is not None:
        filtros.append(Arrecadacao.exercicio == exercicio)
    if mes is not None:
        filtros.append(Arrecadacao.mes == mes)
    if cod_item_receita:
        filtros.append(Arrecadacao.cod_item_receita == cod_item_receita)
    if busca:
        filtros.append(Arrecadacao.descricao_receita.ilike(f"%{busca}%"))

    for f in filtros:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()
    offset = (pagina - 1) * tamanho_pagina
    result = await db.execute(
        query.order_by(
            Arrecadacao.exercicio.desc(),
            Arrecadacao.mes.desc(),
            Arrecadacao.cod_item_receita,
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
# Séries e agregações
# ──────────────────────────────────────────


@router.get("/por-exercicio", response_model=list[SerieAnualArrecadacaoOut])
async def por_exercicio(db: AsyncSession = Depends(get_db)):
    """Série anual de arrecadação total (soma da arrecadação mensal)."""
    query = (
        select(
            Arrecadacao.exercicio,
            func.coalesce(
                func.sum(Arrecadacao.valor_arrecadado_periodo), 0
            ).label("valor"),
        )
        .group_by(Arrecadacao.exercicio)
        .order_by(Arrecadacao.exercicio)
    )
    result = await db.execute(query)
    return [
        SerieAnualArrecadacaoOut(exercicio=r.exercicio, valor=float(r.valor))
        for r in result.all()
    ]


@router.get("/por-mes", response_model=list[SerieMensalArrecadacaoOut])
async def por_mes(
    exercicio: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Série mensal de arrecadação de um exercício."""
    query = (
        select(
            Arrecadacao.mes,
            func.coalesce(
                func.sum(Arrecadacao.valor_arrecadado_periodo), 0
            ).label("valor"),
        )
        .where(Arrecadacao.exercicio == exercicio)
        .group_by(Arrecadacao.mes)
        .order_by(Arrecadacao.mes)
    )
    result = await db.execute(query)
    return [
        SerieMensalArrecadacaoOut(mes=r.mes, valor=float(r.valor))
        for r in result.all()
    ]


@router.get("/por-especie", response_model=list[AgregacaoEspecieOut])
async def por_especie(
    exercicio: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Agregação por espécie tributária (derivada do prefixo do código)."""
    especie_col = _especie_case().label("especie")
    query = (
        select(
            especie_col,
            func.coalesce(
                func.sum(Arrecadacao.valor_arrecadado_periodo), 0
            ).label("valor"),
        )
        .where(Arrecadacao.exercicio == exercicio)
        .group_by(especie_col)
        .order_by(func.sum(Arrecadacao.valor_arrecadado_periodo).desc().nullslast())
    )
    result = await db.execute(query)
    rows = result.all()
    total = sum(float(r.valor) for r in rows) or 1.0
    return [
        AgregacaoEspecieOut(
            especie=r.especie,
            valor=float(r.valor),
            pct=(float(r.valor) / total) * 100,
        )
        for r in rows
    ]


@router.get("/top-tributos", response_model=list[TopTributoOut])
async def top_tributos(
    exercicio: int = Query(...),
    limite: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Top-N itens de receita por valor arrecadado."""
    soma = func.coalesce(func.sum(Arrecadacao.valor_arrecadado_periodo), 0)
    query = (
        select(
            Arrecadacao.cod_item_receita,
            func.max(Arrecadacao.descricao_receita).label("descricao_receita"),
            soma.label("valor"),
        )
        .where(Arrecadacao.exercicio == exercicio)
        .group_by(Arrecadacao.cod_item_receita)
        .order_by(soma.desc().nullslast())
        .limit(limite)
    )
    result = await db.execute(query)
    rows = result.all()

    # Total do exercício para cálculo do percentual.
    total_res = await db.execute(
        select(func.coalesce(func.sum(Arrecadacao.valor_arrecadado_periodo), 0)).where(
            Arrecadacao.exercicio == exercicio
        )
    )
    total = float(total_res.scalar_one() or 0) or 1.0

    return [
        TopTributoOut(
            cod_item_receita=r.cod_item_receita,
            descricao_receita=r.descricao_receita or "",
            valor=float(r.valor),
            pct=(float(r.valor) / total) * 100,
        )
        for r in rows
    ]


@router.get("/ano-x-especie", response_model=list[AnoEspecieOut])
async def ano_x_especie(db: AsyncSession = Depends(get_db)):
    """Matriz ano × espécie para barras empilhadas."""
    especie_col = _especie_case().label("especie")
    query = (
        select(
            Arrecadacao.exercicio,
            especie_col,
            func.coalesce(
                func.sum(Arrecadacao.valor_arrecadado_periodo), 0
            ).label("valor"),
        )
        .group_by(Arrecadacao.exercicio, especie_col)
        .order_by(Arrecadacao.exercicio, especie_col)
    )
    result = await db.execute(query)
    return [
        AnoEspecieOut(
            exercicio=r.exercicio, especie=r.especie, valor=float(r.valor)
        )
        for r in result.all()
    ]


@router.get("/por-banco", response_model=list[AgregacaoBancoOut])
async def por_banco(
    exercicio: int = Query(...),
    mes: int | None = Query(None, ge=1, le=12),
    limite: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Agregação por banco recebedor a partir de recolhimento_detalhe."""
    soma = func.coalesce(func.sum(RecolhimentoDetalhe.valor), 0)
    query = (
        select(RecolhimentoDetalhe.banco, soma.label("valor"))
        .where(RecolhimentoDetalhe.exercicio == exercicio)
        .group_by(RecolhimentoDetalhe.banco)
        .order_by(soma.desc().nullslast())
        .limit(limite)
    )
    if mes is not None:
        query = query.where(RecolhimentoDetalhe.mes == mes)

    result = await db.execute(query)
    rows = result.all()

    total_query = select(func.coalesce(func.sum(RecolhimentoDetalhe.valor), 0)).where(
        RecolhimentoDetalhe.exercicio == exercicio
    )
    if mes is not None:
        total_query = total_query.where(RecolhimentoDetalhe.mes == mes)
    total = float((await db.execute(total_query)).scalar_one() or 0) or 1.0

    return [
        AgregacaoBancoOut(
            banco=r.banco,
            valor=float(r.valor),
            pct=(float(r.valor) / total) * 100,
        )
        for r in rows
    ]


@router.get("/resumo", response_model=ResumoArrecadacaoOut)
async def resumo(
    exercicio: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """KPIs do exercício: total arrecadado, previsto, % realização, delta YoY."""
    # `valor_arrecadado_periodo` é mensal (soma direta). Já `valor_atualizado`
    # carrega a LOA anual e é **repetido** em todas as competências do mesmo
    # (cod_item_receita, cod_fonte_recurso) — somar cru infla o previsto pelo
    # número de meses ingeridos. Colapsamos via subquery que toma MAX por
    # (item, fonte) antes de somar. MAX (em vez de último mês) também tolera
    # retificações de LOA ao longo do ano, ficando com a maior janela vigente.
    prev_sub = (
        select(
            func.max(Arrecadacao.valor_atualizado).label("valor_anual"),
        )
        .where(
            Arrecadacao.exercicio == exercicio,
            Arrecadacao.valor_atualizado.is_not(None),
        )
        .group_by(
            Arrecadacao.cod_item_receita,
            Arrecadacao.cod_fonte_recurso,
        )
        .subquery()
    )

    totais = await db.execute(
        select(
            func.coalesce(func.sum(Arrecadacao.valor_arrecadado_periodo), 0).label(
                "total_arrecadado"
            ),
            func.count(func.distinct(Arrecadacao.cod_item_receita)).label("n_tributos"),
        ).where(Arrecadacao.exercicio == exercicio)
    )
    row = totais.one()
    total_arrec = float(row.total_arrecadado or 0)

    total_prev_raw = (
        await db.execute(select(func.coalesce(func.sum(prev_sub.c.valor_anual), 0)))
    ).scalar_one()
    total_prev = float(total_prev_raw or 0)

    pct = (total_arrec / total_prev * 100) if total_prev > 0 else None

    # Delta YoY (arrecadação deste exercício vs. ano anterior).
    res_anterior = await db.execute(
        select(func.coalesce(func.sum(Arrecadacao.valor_arrecadado_periodo), 0)).where(
            Arrecadacao.exercicio == exercicio - 1
        )
    )
    total_anterior = float(res_anterior.scalar_one() or 0)
    delta = None
    if total_anterior > 0:
        delta = (total_arrec - total_anterior) / total_anterior * 100

    return ResumoArrecadacaoOut(
        exercicio=exercicio,
        total_arrecadado=total_arrec,
        total_previsto=total_prev or None,
        pct_realizacao=pct,
        delta_yoy=delta,
        n_tributos=int(row.n_tributos or 0),
    )


# ────────────────────────────────────────────
# Visão histórica (plurianual) — 2º painel de BI do sócio
# ────────────────────────────────────────────


@router.get("/historico/por-receita", response_model=list[PorReceitaContabilOut])
async def historico_por_receita(
    ano_inicio: int = Query(..., ge=1900, le=2100),
    ano_fim: int = Query(..., ge=1900, le=2100),
    limite: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Ranking plurianual de receitas contábeis: top-N por total no intervalo,
    com valores desagregados por ano. Usado na tabela pivot do painel
    'Arrecadação por Receita Contábil'.
    """
    if ano_fim < ano_inicio:
        ano_inicio, ano_fim = ano_fim, ano_inicio

    # 1 query retorna (cod, descricao, ano, valor). Pivot em Python mantendo
    # o número de queries fixo.
    query = (
        select(
            Arrecadacao.cod_item_receita,
            func.max(Arrecadacao.descricao_receita).label("descricao_receita"),
            Arrecadacao.exercicio,
            func.coalesce(
                func.sum(Arrecadacao.valor_arrecadado_periodo), 0
            ).label("valor"),
        )
        .where(
            Arrecadacao.exercicio.between(ano_inicio, ano_fim),
        )
        .group_by(Arrecadacao.cod_item_receita, Arrecadacao.exercicio)
    )
    result = await db.execute(query)

    pivot: dict[str, dict] = {}
    for r in result.all():
        entry = pivot.setdefault(
            r.cod_item_receita,
            {
                "cod_item_receita": r.cod_item_receita,
                "descricao_receita": r.descricao_receita or "",
                "total": 0.0,
                "por_ano": {},
            },
        )
        valor = float(r.valor or 0)
        entry["por_ano"][r.exercicio] = valor
        entry["total"] += valor
        # Mais longa costuma ser mais completa (casos de descrição truncada
        # em anos antigos do portal).
        if len(r.descricao_receita or "") > len(entry["descricao_receita"]):
            entry["descricao_receita"] = r.descricao_receita or ""

    ordenado = sorted(pivot.values(), key=lambda e: e["total"], reverse=True)
    return [PorReceitaContabilOut(**e) for e in ordenado[:limite]]


@router.get("/historico/mes-x-ano", response_model=list[MesAnoArrecadacaoOut])
async def historico_mes_x_ano(
    ano_inicio: int = Query(..., ge=1900, le=2100),
    ano_fim: int = Query(..., ge=1900, le=2100),
    db: AsyncSession = Depends(get_db),
):
    """
    Matriz mês × ano para barras empilhadas plurianuais. Frontend faz
    o pivot final para gerar `{mes, 2020: X, 2021: Y, ...}`.
    """
    if ano_fim < ano_inicio:
        ano_inicio, ano_fim = ano_fim, ano_inicio

    query = (
        select(
            Arrecadacao.exercicio.label("ano"),
            Arrecadacao.mes,
            func.coalesce(
                func.sum(Arrecadacao.valor_arrecadado_periodo), 0
            ).label("valor"),
        )
        .where(
            Arrecadacao.exercicio.between(ano_inicio, ano_fim),
        )
        .group_by(Arrecadacao.exercicio, Arrecadacao.mes)
        .order_by(Arrecadacao.exercicio, Arrecadacao.mes)
    )
    result = await db.execute(query)
    return [
        MesAnoArrecadacaoOut(ano=r.ano, mes=r.mes, valor=float(r.valor))
        for r in result.all()
    ]
