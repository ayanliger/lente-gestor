"""
Serviço de ingestão de arrecadação tributária do Município Online.

Fluxo em dois passos por (exercicio, mes):

1. **Agregado** — `MunicipioOnlineClient.listar_receitas(ano, mes)` devolve
   a lista de itens de receita (× fonte de recursos) daquele mês.
   Cada registro vira um upsert em `arrecadacao`.

2. **Drill-down** — para cada linha agregada, `obter_recolhimentos(keys)`
   devolve os recolhimentos individuais com data, banco, valor. Cada
   recolhimento vira um upsert em `recolhimento_detalhe`.

A flag `com_detalhes=False` pula o passo 2 (útil para backfill rápido
do agregado histórico).
"""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors.municipio_online import MunicipioOnlineClient
from app.db.session import async_session
from app.models.arrecadacao import Arrecadacao, RecolhimentoDetalhe
from app.models.contratacoes import Orgao

logger = structlog.get_logger()
settings = get_settings()

MESES_PADRAO = list(range(1, 13))  # 1..12
FONTE_MUNICIPIO_ONLINE = "MUNICIPIO_ONLINE"


# ──────────────────────────────────────────
# Parsers / normalizadores
# ──────────────────────────────────────────


def _parse_decimal(value: object) -> Decimal | None:
    """
    Converte valor do portal para Decimal.

    Aceita:
      - None ou string vazia → None
      - Número já tipado
      - String no formato brasileiro ("R$ 1.234.567,89" ou "1.234,56")
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    texto = str(value).strip()
    if not texto:
        return None
    # Remove "R$", espaços não-quebráveis e espaços comuns.
    texto = (
        texto.replace("R$", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .strip()
    )
    if not texto:
        return None
    # Formato BR: ponto = milhar, vírgula = decimal.
    # Se houver ambos, substitui ponto por nada e vírgula por ponto.
    # Se só houver vírgula, substitui por ponto.
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _parse_data_br(value: object) -> date | None:
    """Converte string dd/mm/yyyy (ou dd/mm/yy) para date."""
    if not value:
        return None
    texto = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _classificar_especie(cod_item_receita: str | None) -> str:
    """
    Deriva a espécie tributária a partir do prefixo do código do Tesouro.

    Taxonomia baseada no Manual de Contabilidade Aplicada ao Setor Público
    (MCASP) e nos códigos de Natureza da Receita do STN:

        1111*  Impostos sobre Patrimônio       → "Impostos"
        1112*  Impostos sobre Renda            → "Impostos"
        1113*  Impostos sobre Produção         → "Impostos"
        1114*  Impostos sobre Serviços         → "Impostos"
        111*   demais impostos                 → "Impostos"
        112*   Taxas                           → "Taxas"
        113*   Contribuição de Melhoria        → "Contribuição de Melhoria"
        12*    Contribuições                   → "Contribuições"
        13*    Receita Patrimonial             → "Patrimonial"
        14*    Receita Agropecuária            → "Agropecuária"
        15*    Receita Industrial              → "Industrial"
        16*    Receita de Serviços             → "Serviços"
        17*    Transferências Correntes        → "Transferências"
        19*    Outras Receitas Correntes       → "Não Tributária"
        2*     Receitas de Capital             → "Capital"
        7*/8*  Intraorçamentárias              → "Intraorçamentária"

    Códigos vazios ou desconhecidos → "Outras".
    """
    if not cod_item_receita:
        return "Outras"
    cod = str(cod_item_receita).strip()
    if not cod:
        return "Outras"

    # Impostos (111*)
    if cod.startswith("111"):
        return "Impostos"
    # Taxas (112*)
    if cod.startswith("112"):
        return "Taxas"
    # Contribuição de Melhoria (113*)
    if cod.startswith("113"):
        return "Contribuição de Melhoria"
    # Contribuições (12*)
    if cod.startswith("12"):
        return "Contribuições"
    # Patrimonial (13*)
    if cod.startswith("13"):
        return "Patrimonial"
    # Agropecuária (14*)
    if cod.startswith("14"):
        return "Agropecuária"
    # Industrial (15*)
    if cod.startswith("15"):
        return "Industrial"
    # Serviços (16*)
    if cod.startswith("16"):
        return "Serviços"
    # Transferências Correntes (17*)
    if cod.startswith("17"):
        return "Transferências"
    # Outras Receitas Correntes (19*)
    if cod.startswith("19"):
        return "Não Tributária"
    # Receitas de Capital (2*)
    if cod.startswith("2"):
        return "Capital"
    # Intraorçamentárias (7*/8*)
    if cod.startswith(("7", "8")):
        return "Intraorçamentária"
    return "Outras"


def _extrair_ano_mes(keys: dict) -> tuple[int | None, int | None]:
    """Extrai (ano, mes) do campo `DtAnoMes` da linha agregada (formato YYYYMM)."""
    dt_ano_mes = str(keys.get("DtAnoMes", "") or "").strip()
    if len(dt_ano_mes) != 6 or not dt_ano_mes.isdigit():
        return None, None
    try:
        ano = int(dt_ano_mes[:4])
        mes = int(dt_ano_mes[4:])
    except ValueError:
        return None, None
    if not (1 <= mes <= 12):
        return None, None
    return ano, mes


def _normalizar_agregado(raw: dict, exercicio: int, mes: int) -> dict:
    """
    Normaliza um registro agregado vindo do portal para campos do modelo.

    O portal devolve o mês real de referência dentro de `DtAnoMes` (campo do
    `data-key`). Em alguns casos ele ignora o filtro enviado pelo cliente e
    retorna dados de outro mês. Para evitar duplicações, usamos o
    `DtAnoMes` como fonte de verdade quando disponível.
    """
    keys = raw.get("keys") or {}
    cod_item_receita = raw.get("cod_item_receita") or str(keys.get("CdItemReceita", ""))

    ano_real, mes_real = _extrair_ano_mes(keys)
    if ano_real is not None and mes_real is not None:
        if ano_real != exercicio or mes_real != mes:
            logger.info(
                "ingestao.arrecadacao.mes_divergente",
                mes_solicitado=mes,
                ano_solicitado=exercicio,
                mes_portal=mes_real,
                ano_portal=ano_real,
                cod_item=cod_item_receita,
            )
        exercicio = ano_real
        mes = mes_real

    return {
        "exercicio": exercicio,
        "mes": mes,
        "data_emissao": _parse_data_br(raw.get("data_emissao")),
        "cod_item_receita": cod_item_receita,
        "descricao_receita": (raw.get("descricao_receita") or "")[:500],
        "poder": raw.get("poder") or None,
        "categoria": raw.get("categoria") or None,
        "cod_fonte_recurso": raw.get("cod_fonte_recurso"),
        "descricao_fonte_recurso": (raw.get("descricao_fonte_recurso") or "")[:500]
        or None,
        "valor_previsto": _parse_decimal(raw.get("valor_previsto")),
        "valor_atualizado": _parse_decimal(raw.get("valor_atualizado")),
        "valor_arrecadado_periodo": _parse_decimal(raw.get("valor_arrecadado_periodo")),
        "valor_arrecadado_acumulado": _parse_decimal(
            raw.get("valor_arrecadado_acumulado")
        ),
        "fonte": FONTE_MUNICIPIO_ONLINE,
        "dados_brutos": json.dumps(raw, ensure_ascii=False, default=str),
    }


def _normalizar_recolhimento(raw: dict) -> dict:
    """Normaliza um recolhimento individual vindo do drill-down."""
    return {
        "data_emissao": _parse_data_br(raw.get("DtEmissao")),
        "numero_processo": raw.get("NuProcesso") or None,
        "banco": (raw.get("DsContaBanco") or "").strip() or "(não informado)",
        "historico": raw.get("DsHistorico") or None,
        "valor": _parse_decimal(raw.get("VlRecolhimento")),
        "dados_brutos": json.dumps(raw, ensure_ascii=False, default=str),
    }


# ──────────────────────────────────────────
# Upsert do órgão (derivado do portal)
# ──────────────────────────────────────────


async def _upsert_orgao_from_municipio_online(db: AsyncSession, raw: dict) -> Orgao:
    """
    Retorna (ou cria) o Orgao correspondente ao município.

    O portal não traz CNPJ no payload agregado de forma explícita, mas
    conhecemos o CNPJ do município (config). Enriquece razão social
    com o texto "orgao" exibido na listagem quando aplicável.
    """
    cnpj = settings.pncp_cnpj_jequie

    result = await db.execute(select(Orgao).where(Orgao.cnpj == cnpj))
    orgao = result.scalar_one_or_none()

    razao = (raw.get("orgao") or "").strip() or f"MUNICÍPIO {cnpj}"

    if orgao:
        # Enriquecer razão social se estiver genérica.
        if raw.get("orgao") and (not orgao.razao_social or "MUNICÍPIO" in orgao.razao_social):
            orgao.razao_social = razao
        return orgao

    orgao = Orgao(
        cnpj=cnpj,
        razao_social=razao,
        esfera="M",
    )
    db.add(orgao)
    await db.flush()
    logger.info("ingestao.arrecadacao.orgao_criado", cnpj=cnpj, razao=razao)
    return orgao


# ──────────────────────────────────────────
# Upsert helpers (chave única composta)
# ──────────────────────────────────────────


async def _upsert_arrecadacao(
    db: AsyncSession, campos: dict, orgao_id, cod_ibge: str, stats: dict
) -> Arrecadacao:
    chave = {
        "orgao_id": orgao_id,
        "exercicio": campos["exercicio"],
        "mes": campos["mes"],
        "cod_item_receita": campos["cod_item_receita"],
        "cod_fonte_recurso": campos["cod_fonte_recurso"],
    }
    result = await db.execute(select(Arrecadacao).filter_by(**chave))
    existing = result.scalar_one_or_none()
    if existing:
        for k, v in campos.items():
            setattr(existing, k, v)
        existing.orgao_id = orgao_id
        existing.cod_ibge = cod_ibge
        stats["agregado_atualizados"] += 1
        return existing

    registro = Arrecadacao(**campos, orgao_id=orgao_id, cod_ibge=cod_ibge)
    db.add(registro)
    await db.flush()
    stats["agregado_criados"] += 1
    return registro


async def _upsert_recolhimento(
    db: AsyncSession,
    campos: dict,
    arrecadacao_id,
    orgao_id,
    exercicio: int,
    mes: int,
    stats: dict,
) -> None:
    chave = {
        "arrecadacao_id": arrecadacao_id,
        "numero_processo": campos.get("numero_processo"),
        "banco": campos["banco"],
        "data_emissao": campos.get("data_emissao"),
        "valor": campos.get("valor"),
    }
    result = await db.execute(select(RecolhimentoDetalhe).filter_by(**chave))
    existing = result.scalar_one_or_none()
    if existing:
        existing.historico = campos.get("historico")
        existing.dados_brutos = campos.get("dados_brutos")
        stats["detalhe_atualizados"] += 1
        return

    registro = RecolhimentoDetalhe(
        **campos,
        arrecadacao_id=arrecadacao_id,
        orgao_id=orgao_id,
        exercicio=exercicio,
        mes=mes,
    )
    db.add(registro)
    stats["detalhe_criados"] += 1


# ──────────────────────────────────────────
# Pipeline público
# ──────────────────────────────────────────


async def ingerir_arrecadacao(
    exercicio: int,
    meses: list[int] | None = None,
    com_detalhes: bool = False,
) -> dict:
    """
    Ingestão de arrecadação tributária para (exercicio, meses).

    Fluxo por mês:
      1. GET/POST agregado → upsert em `arrecadacao`
      2. (opcional) Para cada item agregado, drill-down → upsert em
         `recolhimento_detalhe`

    O drill-down é **desabilitado por padrão** (`com_detalhes=False`)
    porque gera centenas de requests por mês contra o portal público.
    A visualização “Arrecadação por banco recebedor” depende desses
    dados, mas está oculta no frontend por hora. Para reabilitá-la,
    rode a ingestão com `com_detalhes=True`.

    Retorna contadores de stats. Um mês com falha no fetch não interrompe
    os demais.
    """
    meses = meses or MESES_PADRAO
    stats = {
        "agregado_criados": 0,
        "agregado_atualizados": 0,
        "detalhe_criados": 0,
        "detalhe_atualizados": 0,
        "erros": 0,
        "meses_processados": 0,
    }
    cod_ibge = settings.siconfi_id_ente_jequie

    async with MunicipioOnlineClient() as cliente:
        for mes in meses:
            try:
                registros = await cliente.listar_receitas(exercicio, mes)
            except Exception as e:
                logger.error(
                    "ingestao.arrecadacao.fetch_erro",
                    exercicio=exercicio,
                    mes=mes,
                    erro=str(e),
                )
                stats["erros"] += 1
                continue

            async with async_session() as db:
                orgao: Orgao | None = None
                # Itens já consultados no drill-down nesse mês — cada item
                # costuma ter N fontes de recursos no agregado; o drill-down
                # é por item, não por fonte, então consultamos uma vez só.
                itens_detalhados: set[tuple[str, int, int]] = set()

                for raw in registros:
                    try:
                        if orgao is None:
                            orgao = await _upsert_orgao_from_municipio_online(db, raw)

                        campos = _normalizar_agregado(raw, exercicio, mes)
                        if not campos["cod_item_receita"]:
                            logger.warning(
                                "ingestao.arrecadacao.item_sem_codigo",
                                exercicio=exercicio,
                                mes=mes,
                            )
                            continue

                        # Se o portal devolveu linha de outro exercício, não
                        # contamina o ano solicitado — vai ser captado quando
                        # o ano correto for ingerido.
                        if campos["exercicio"] != exercicio:
                            continue

                        arrecadacao = await _upsert_arrecadacao(
                            db, campos, orgao.id, cod_ibge, stats
                        )

                        if com_detalhes:
                            chave_detalhe = (
                                arrecadacao.cod_item_receita,
                                arrecadacao.exercicio,
                                arrecadacao.mes,
                            )
                            if chave_detalhe not in itens_detalhados:
                                itens_detalhados.add(chave_detalhe)
                                await _ingerir_detalhes(
                                    cliente,
                                    db,
                                    raw.get("keys") or {},
                                    arrecadacao,
                                    orgao.id,
                                    arrecadacao.exercicio,
                                    arrecadacao.mes,
                                    stats,
                                )

                    except Exception as e:
                        logger.error(
                            "ingestao.arrecadacao.item_erro",
                            exercicio=exercicio,
                            mes=mes,
                            erro=str(e),
                        )
                        stats["erros"] += 1

                await db.commit()

            stats["meses_processados"] += 1
            logger.info(
                "ingestao.arrecadacao.mes_concluido",
                exercicio=exercicio,
                mes=mes,
                total_registros=len(registros),
            )

    logger.info("ingestao.arrecadacao.concluida", exercicio=exercicio, **stats)
    return stats


async def _ingerir_detalhes(
    cliente: MunicipioOnlineClient,
    db: AsyncSession,
    keys: dict,
    arrecadacao: Arrecadacao,
    orgao_id,
    exercicio: int,
    mes: int,
    stats: dict,
) -> None:
    """
    Drill-down de uma linha agregada: busca recolhimentos e faz upsert.

    Só deve ser chamado uma vez por `cod_item_receita × mes × ano` —
    a deduplicação é feita pelo chamador via `itens_detalhados`.
    """
    if not keys:
        return

    try:
        recolhimentos_raw = await cliente.obter_recolhimentos(keys)
    except Exception as e:
        logger.warning(
            "ingestao.arrecadacao.drill_down_erro",
            cod_item=arrecadacao.cod_item_receita,
            erro=str(e),
        )
        return

    for raw in recolhimentos_raw:
        campos = _normalizar_recolhimento(raw)
        if not campos.get("banco"):
            continue
        await _upsert_recolhimento(
            db, campos, arrecadacao.id, orgao_id, exercicio, mes, stats
        )
