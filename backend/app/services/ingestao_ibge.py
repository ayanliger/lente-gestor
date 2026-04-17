"""
Serviço de ingestão de dados contextuais do IBGE.

Busca metadados do município, série de população e série de PIB;
cria/atualiza uma linha por exercício em `dados_municipio`, calculando
`pib_per_capita` quando população e PIB estiverem ambos disponíveis.
"""

import json
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors.ibge import IBGEClient
from app.db.session import async_session
from app.models.contratacoes import Orgao
from app.models.orcamento import DadosMunicipio

logger = structlog.get_logger()
settings = get_settings()

FONTE_IBGE = "IBGE"
# PIB SIDRA vem em "Mil Reais" (multiplicar por 1000 para obter reais).
FATOR_MIL_REAIS = Decimal(1000)


def _parse_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return None


def _parse_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _extrair_serie(payload: list) -> dict[int, str]:
    """
    Achata um payload SIDRA v3 em `{exercicio: valor_str}`.

    Estrutura esperada: `[{resultados: [{series: [{serie: {ano: valor, ...}}]}]}]`.
    Retorna dict vazio para payloads ausentes ou malformados.
    """
    if not payload or not isinstance(payload, list):
        return {}
    try:
        resultados = payload[0].get("resultados", []) or []
        if not resultados:
            return {}
        series = resultados[0].get("series", []) or []
        if not series:
            return {}
        serie = series[0].get("serie", {}) or {}
    except (AttributeError, IndexError, TypeError):
        return {}

    saida: dict[int, str] = {}
    for ano_str, valor in serie.items():
        ano = _parse_int(ano_str)
        if ano is None:
            continue
        saida[ano] = valor
    return saida


def _extrair_uf_nome(metadata: dict) -> tuple[str | None, str | None]:
    """Extrai (uf_sigla, nome_municipio) do dict aninhado de /localidades."""
    nome = metadata.get("nome")
    uf: str | None = None
    try:
        microrregiao = metadata.get("microrregiao") or {}
        mesorregiao = microrregiao.get("mesorregiao") or {}
        uf_obj = mesorregiao.get("UF") or {}
        uf = uf_obj.get("sigla")
    except AttributeError:
        uf = None
    return uf, nome


async def _upsert_orgao_from_ibge(db: AsyncSession, metadata: dict) -> Orgao:
    """
    Insere ou retorna o Orgao do município. Usa o CNPJ configurado;
    em caso de órgão pré-existente, enriquece UF/município se faltarem.
    """
    cnpj = settings.pncp_cnpj_jequie

    result = await db.execute(select(Orgao).where(Orgao.cnpj == cnpj))
    orgao = result.scalar_one_or_none()

    uf, nome = _extrair_uf_nome(metadata)

    if orgao:
        if not orgao.uf and uf:
            orgao.uf = uf
        if not orgao.municipio and nome:
            orgao.municipio = nome
        return orgao

    orgao = Orgao(
        cnpj=cnpj,
        razao_social=f"Município de {nome}" if nome else "",
        esfera="M",
        uf=uf,
        municipio=nome,
    )
    db.add(orgao)
    await db.flush()
    logger.info("ingestao.ibge.orgao_criado", cnpj=cnpj, nome=nome)
    return orgao


async def ingerir_ibge(
    codigo_ibge: str | None = None,
    ultimos_periodos: int = 10,
) -> dict:
    """
    Ingere metadados + população + PIB para um município.

    Retorna contadores: {criados, atualizados, erros, anos_processados}.
    """
    codigo_ibge = codigo_ibge or settings.siconfi_id_ente_jequie
    stats = {"criados": 0, "atualizados": 0, "erros": 0, "anos_processados": 0}

    async with IBGEClient() as ibge:
        try:
            metadata = await ibge.municipio(codigo_ibge)
        except Exception as e:
            logger.error("ingestao.ibge.fetch_metadata_erro", codigo_ibge=codigo_ibge, erro=str(e))
            stats["erros"] += 1
            return stats

        try:
            pop_payload = await ibge.populacao(codigo_ibge, ultimos_periodos=ultimos_periodos)
        except Exception as e:
            logger.error("ingestao.ibge.fetch_populacao_erro", codigo_ibge=codigo_ibge, erro=str(e))
            pop_payload = []
            stats["erros"] += 1

        try:
            pib_payload = await ibge.pib(codigo_ibge, ultimos_periodos=ultimos_periodos)
        except Exception as e:
            logger.error("ingestao.ibge.fetch_pib_erro", codigo_ibge=codigo_ibge, erro=str(e))
            pib_payload = []
            stats["erros"] += 1

    serie_populacao = _extrair_serie(pop_payload)
    serie_pib_mil = _extrair_serie(pib_payload)

    uf, nome = _extrair_uf_nome(metadata)
    anos = sorted(set(serie_populacao.keys()) | set(serie_pib_mil.keys()))

    if not anos:
        logger.warning("ingestao.ibge.sem_dados", codigo_ibge=codigo_ibge)
        return stats

    dados_brutos_blob = json.dumps(
        {"metadata": metadata, "populacao": pop_payload, "pib": pib_payload},
        ensure_ascii=False,
        default=str,
    )

    async with async_session() as db:
        orgao = await _upsert_orgao_from_ibge(db, metadata)

        for ano in anos:
            try:
                populacao = _parse_int(serie_populacao.get(ano))
                pib_mil = _parse_decimal(serie_pib_mil.get(ano))
                pib_corrente = pib_mil * FATOR_MIL_REAIS if pib_mil is not None else None

                pib_per_capita: Decimal | None = None
                if pib_corrente is not None and populacao:
                    pib_per_capita = (pib_corrente / Decimal(populacao)).quantize(Decimal("0.01"))

                result = await db.execute(
                    select(DadosMunicipio).where(
                        DadosMunicipio.orgao_id == orgao.id,
                        DadosMunicipio.exercicio == ano,
                    )
                )
                existing = result.scalar_one_or_none()

                campos = {
                    "codigo_ibge": codigo_ibge,
                    "exercicio": ano,
                    "nome_municipio": nome,
                    "uf": uf,
                    "populacao": populacao,
                    "pib_corrente": pib_corrente,
                    "pib_per_capita": pib_per_capita,
                    "fonte": FONTE_IBGE,
                    "dados_brutos": dados_brutos_blob,
                }

                if existing:
                    for k, v in campos.items():
                        setattr(existing, k, v)
                    existing.orgao_id = orgao.id
                    stats["atualizados"] += 1
                else:
                    registro = DadosMunicipio(**campos, orgao_id=orgao.id)
                    db.add(registro)
                    stats["criados"] += 1

                stats["anos_processados"] += 1
            except Exception as e:
                logger.error("ingestao.ibge.ano_erro", ano=ano, erro=str(e))
                stats["erros"] += 1

        await db.commit()

    logger.info("ingestao.ibge.concluida", codigo_ibge=codigo_ibge, **stats)
    return stats
