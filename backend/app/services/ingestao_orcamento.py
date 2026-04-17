"""
Serviço de ingestão de dados orçamentários do SICONFI para o banco local.

Busca o Relatório Resumido da Execução Orçamentária (RREO) por bimestre,
normaliza cada célula e persiste em `execucao_orcamentaria` via upsert.

Fase 1: apenas RREO. RGF e DCA entram em fases posteriores.
"""

import json
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors.siconfi import SICONFIClient
from app.db.session import async_session
from app.models.contratacoes import Orgao
from app.models.orcamento import ExecucaoOrcamentaria

logger = structlog.get_logger()
settings = get_settings()

PERIODOS_RREO_PADRAO = [1, 2, 3, 4, 5, 6]  # bimestres
FONTE_RREO = "SICONFI_RREO"
TIPO_RELATORIO_RREO = "RREO"


def _parse_decimal(value: object) -> Decimal | None:
    """Converte número/str para Decimal; retorna None se vazio/None/inválido."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _normalizar_rreo(raw: dict) -> dict:
    """Mapeia um item do payload RREO para campos do modelo ExecucaoOrcamentaria."""
    cod_ibge = raw.get("cod_ibge")
    return {
        "exercicio": raw.get("exercicio"),
        "periodo": raw.get("periodo"),
        "periodicidade": raw.get("periodicidade"),
        "tipo_relatorio": TIPO_RELATORIO_RREO,
        "anexo": raw.get("anexo"),
        "rotulo": raw.get("rotulo"),
        "coluna": raw.get("coluna"),
        "cod_conta": raw.get("cod_conta"),
        "conta": raw.get("conta"),
        "valor": _parse_decimal(raw.get("valor")),
        "cod_ibge": str(cod_ibge) if cod_ibge is not None else "",
        "fonte": FONTE_RREO,
        "dados_brutos": json.dumps(raw, ensure_ascii=False, default=str),
    }


async def _upsert_orgao_from_siconfi(db: AsyncSession, raw: dict) -> Orgao:
    """
    Insere ou retorna o Orgao correspondente ao ente do SICONFI.

    SICONFI não traz CNPJ; assumimos o CNPJ do município configurado
    (`settings.pncp_cnpj_jequie`). Para outros municípios no futuro,
    este mapeamento deverá usar uma tabela de entes.
    """
    cnpj = settings.pncp_cnpj_jequie

    result = await db.execute(select(Orgao).where(Orgao.cnpj == cnpj))
    orgao = result.scalar_one_or_none()

    instituicao = raw.get("instituicao", "") or ""
    uf = raw.get("uf")
    esfera = raw.get("esfera")
    # "Prefeitura Municipal de Jequié - BA" -> "Jequié"
    municipio: str | None = None
    if " de " in instituicao and " - " in instituicao:
        municipio = instituicao.split(" de ", 1)[1].split(" - ", 1)[0].strip()

    if orgao:
        # Enriquecer campos ausentes a partir da fonte oficial.
        if not orgao.uf and uf:
            orgao.uf = uf
        if not orgao.municipio and municipio:
            orgao.municipio = municipio
        if not orgao.esfera and esfera:
            orgao.esfera = esfera
        return orgao

    orgao = Orgao(
        cnpj=cnpj,
        razao_social=instituicao,
        esfera=esfera,
        uf=uf,
        municipio=municipio,
    )
    db.add(orgao)
    await db.flush()
    logger.info("ingestao.orcamento.orgao_criado", cnpj=cnpj, razao=orgao.razao_social)
    return orgao


def _chave_unica(registro: dict, orgao_id) -> dict:
    """Compõe o filtro da chave única `ix_exec_orc_unique`."""
    return {
        "orgao_id": orgao_id,
        "exercicio": registro["exercicio"],
        "periodo": registro["periodo"],
        "tipo_relatorio": registro["tipo_relatorio"],
        "anexo": registro["anexo"],
        "cod_conta": registro["cod_conta"],
        "coluna": registro["coluna"],
        "conta": registro["conta"],
    }


async def ingerir_rreo(
    exercicio: int,
    periodos: list[int] | None = None,
) -> dict:
    """
    Ingere o RREO de um exercício para os bimestres informados.

    Retorna contadores: {criados, atualizados, erros, periodos_processados}.
    Um período que falhar no fetch não interrompe os demais.
    """
    periodos = periodos or PERIODOS_RREO_PADRAO
    stats = {"criados": 0, "atualizados": 0, "erros": 0, "periodos_processados": 0}

    async with SICONFIClient() as siconfi:
        for periodo in periodos:
            try:
                items = await siconfi.paginar_rreo(
                    an_exercicio=exercicio, nr_periodo=periodo
                )
            except Exception as e:
                logger.error(
                    "ingestao.orcamento.fetch_erro",
                    exercicio=exercicio,
                    periodo=periodo,
                    erro=str(e),
                )
                stats["erros"] += 1
                continue

            async with async_session() as db:
                orgao: Orgao | None = None

                for raw in items:
                    try:
                        if orgao is None:
                            orgao = await _upsert_orgao_from_siconfi(db, raw)

                        campos = _normalizar_rreo(raw)

                        # Validar chave mínima antes do upsert.
                        if not all(
                            [
                                campos["exercicio"] is not None,
                                campos["periodo"] is not None,
                                campos["anexo"],
                                campos["cod_conta"],
                                campos["coluna"],
                            ]
                        ):
                            logger.warning(
                                "ingestao.orcamento.item_incompleto",
                                raw_cod_conta=raw.get("cod_conta"),
                            )
                            continue

                        chave = _chave_unica(campos, orgao.id)
                        result = await db.execute(
                            select(ExecucaoOrcamentaria).filter_by(**chave)
                        )
                        existing = result.scalar_one_or_none()

                        if existing:
                            for k, v in campos.items():
                                setattr(existing, k, v)
                            existing.orgao_id = orgao.id
                            stats["atualizados"] += 1
                        else:
                            registro = ExecucaoOrcamentaria(
                                **campos, orgao_id=orgao.id
                            )
                            db.add(registro)
                            stats["criados"] += 1

                    except Exception as e:
                        logger.error(
                            "ingestao.orcamento.item_erro",
                            exercicio=exercicio,
                            periodo=periodo,
                            erro=str(e),
                        )
                        stats["erros"] += 1

                await db.commit()

            stats["periodos_processados"] += 1
            logger.info(
                "ingestao.orcamento.periodo_concluido",
                exercicio=exercicio,
                periodo=periodo,
                total_items=len(items),
            )

    logger.info("ingestao.orcamento.concluida", exercicio=exercicio, **stats)
    return stats
