"""
Serviço de ingestão de dados do PNCP para o banco de dados local.

Busca contratações e contratos da API do PNCP para o município configurado,
normaliza os dados e persiste via upsert (insert ou atualiza se já existe).
"""

import json
from datetime import date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.pncp import MODALIDADES, PNCPClient
from app.db.session import async_session
from app.models.contratacoes import Contratacao, Contrato, Fornecedor, Orgao

logger = structlog.get_logger()


def _parse_date(value: str | None) -> date | None:
    """Converte string de data PNCP para date. Aceita YYYY-MM-DD ou datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _parse_datetime(value: str | None) -> datetime | None:
    """Converte string datetime PNCP para datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _upsert_orgao(db: AsyncSession, dados: dict) -> Orgao:
    """Insere ou retorna órgão existente pelo CNPJ."""
    cnpj = dados["cnpj"]
    result = await db.execute(select(Orgao).where(Orgao.cnpj == cnpj))
    orgao = result.scalar_one_or_none()
    if orgao:
        return orgao

    orgao = Orgao(
        cnpj=cnpj,
        razao_social=dados.get("razaoSocial", ""),
        esfera=dados.get("esferaId"),
    )
    db.add(orgao)
    await db.flush()
    logger.info("ingestao.orgao_criado", cnpj=cnpj, razao=orgao.razao_social)
    return orgao


async def _upsert_fornecedor(db: AsyncSession, dados: dict) -> Fornecedor:
    """Insere ou retorna fornecedor existente pelo CPF/CNPJ."""
    cpf_cnpj = dados["cpf_cnpj"]
    result = await db.execute(select(Fornecedor).where(Fornecedor.cpf_cnpj == cpf_cnpj))
    fornecedor = result.scalar_one_or_none()
    if fornecedor:
        return fornecedor

    fornecedor = Fornecedor(
        cpf_cnpj=cpf_cnpj,
        nome=dados.get("nome", ""),
        tipo=dados.get("tipo"),
    )
    db.add(fornecedor)
    await db.flush()
    logger.info("ingestao.fornecedor_criado", cpf_cnpj=cpf_cnpj, nome=fornecedor.nome)
    return fornecedor


def _normalizar_contratacao(raw: dict) -> dict:
    """Mapeia campos da API PNCP para o modelo Contratacao."""
    return {
        "pncp_id": raw.get("numeroControlePNCP"),
        "numero_sequencial": raw.get("sequencialCompra"),
        "ano": raw.get("anoCompra"),
        "numero_processo": raw.get("processo"),
        "modalidade": raw.get("modalidadeNome"),
        "tipo": raw.get("tipoInstrumentoConvocatorioNome"),
        "objeto": raw.get("objetoCompra"),
        "valor_estimado": raw.get("valorTotalEstimado"),
        "valor_homologado": raw.get("valorTotalHomologado"),
        "situacao": raw.get("situacaoCompraNome"),
        "data_publicacao": _parse_date(raw.get("dataPublicacaoPncp")),
        "data_abertura": _parse_date(raw.get("dataAberturaProposta")),
        "fonte": "pncp",
        "dados_brutos": json.dumps(raw, ensure_ascii=False, default=str),
    }


def _normalizar_contrato(raw: dict) -> dict:
    """Mapeia campos da API PNCP para o modelo Contrato."""
    return {
        "pncp_id": raw.get("numeroControlePNCP"),
        "numero_contrato": raw.get("numeroContratoEmpenho"),
        "ano": raw.get("anoContrato"),
        "objeto": raw.get("objetoContrato"),
        "valor_inicial": raw.get("valorInicial"),
        "valor_atual": raw.get("valorGlobal"),
        "data_assinatura": _parse_date(raw.get("dataAssinatura")),
        "data_inicio_vigencia": _parse_date(raw.get("dataVigenciaInicio")),
        "data_fim_vigencia": _parse_date(raw.get("dataVigenciaFim")),
        "categoria": (raw.get("categoriaProcesso") or {}).get("nome"),
        "fonte": "pncp",
        "dados_brutos": json.dumps(raw, ensure_ascii=False, default=str),
    }


async def ingerir_contratacoes(
    data_inicial: date,
    data_final: date,
    modalidades: list[int] | None = None,
) -> dict:
    """
    Ingere contratações do PNCP para todas as modalidades relevantes.

    Retorna contadores: {criadas, atualizadas, erros}.
    """
    modalidades = modalidades or list(MODALIDADES.keys())
    stats = {"criadas": 0, "atualizadas": 0, "erros": 0}

    async with PNCPClient() as pncp:
        for mod in modalidades:
            logger.info("ingestao.contratacoes.modalidade", modalidade=mod, nome=MODALIDADES.get(mod))

            try:
                registros = await pncp.paginar_todos(
                    pncp.listar_contratacoes,
                    tamanho_pagina=50,  # Contratacoes aceita max ~50
                    data_inicial=data_inicial,
                    data_final=data_final,
                    codigo_modalidade=mod,
                )
            except Exception as e:
                logger.error("ingestao.contratacoes.fetch_erro", modalidade=mod, erro=str(e))
                stats["erros"] += 1
                continue

            async with async_session() as db:
                for raw in registros:
                    try:
                        pncp_id = raw.get("numeroControlePNCP")
                        if not pncp_id:
                            continue

                        # Upsert órgão
                        orgao_data = raw.get("orgaoEntidade", {})
                        orgao = await _upsert_orgao(db, orgao_data)

                        # Verificar se já existe
                        result = await db.execute(
                            select(Contratacao).where(Contratacao.pncp_id == pncp_id)
                        )
                        existing = result.scalar_one_or_none()

                        campos = _normalizar_contratacao(raw)

                        if existing:
                            for k, v in campos.items():
                                setattr(existing, k, v)
                            existing.orgao_id = orgao.id
                            stats["atualizadas"] += 1
                        else:
                            contratacao = Contratacao(**campos, orgao_id=orgao.id)
                            db.add(contratacao)
                            stats["criadas"] += 1

                    except Exception as e:
                        logger.error("ingestao.contratacao.erro", pncp_id=pncp_id, erro=str(e))
                        stats["erros"] += 1

                await db.commit()

    logger.info("ingestao.contratacoes.concluida", **stats)
    return stats


async def ingerir_contratos(
    data_inicial: date,
    data_final: date,
) -> dict:
    """
    Ingere contratos do PNCP.

    A API limita a 365 dias por requisição; esta função respeita esse limite.
    Retorna contadores: {criados, atualizados, erros}.
    """
    stats = {"criados": 0, "atualizados": 0, "erros": 0}

    async with PNCPClient() as pncp:
        try:
            registros = await pncp.paginar_todos(
                pncp.listar_contratos,
                data_inicial=data_inicial,
                data_final=data_final,
            )
        except Exception as e:
            logger.error("ingestao.contratos.fetch_erro", erro=str(e))
            return stats

    async with async_session() as db:
        for raw in registros:
            try:
                pncp_id = raw.get("numeroControlePNCP")
                if not pncp_id:
                    continue

                # Upsert órgão
                orgao_data = raw.get("orgaoEntidade", {})
                if orgao_data:
                    await _upsert_orgao(db, orgao_data)

                # Upsert fornecedor
                ni_fornecedor = raw.get("niFornecedor")
                fornecedor = None
                if ni_fornecedor:
                    fornecedor = await _upsert_fornecedor(db, {
                        "cpf_cnpj": ni_fornecedor,
                        "nome": raw.get("nomeRazaoSocialFornecedor", ""),
                        "tipo": raw.get("tipoPessoa"),
                    })

                # Vincular à contratação se existir
                contratacao_pncp_id = raw.get("numeroControlePncpCompra")
                contratacao_id = None
                if contratacao_pncp_id:
                    result = await db.execute(
                        select(Contratacao.id).where(Contratacao.pncp_id == contratacao_pncp_id)
                    )
                    row = result.scalar_one_or_none()
                    if row:
                        contratacao_id = row

                # Upsert contrato
                result = await db.execute(
                    select(Contrato).where(Contrato.pncp_id == pncp_id)
                )
                existing = result.scalar_one_or_none()

                campos = _normalizar_contrato(raw)

                if existing:
                    for k, v in campos.items():
                        setattr(existing, k, v)
                    if fornecedor:
                        existing.fornecedor_id = fornecedor.id
                    if contratacao_id:
                        existing.contratacao_id = contratacao_id
                    stats["atualizados"] += 1
                else:
                    contrato = Contrato(
                        **campos,
                        fornecedor_id=fornecedor.id if fornecedor else None,
                        contratacao_id=contratacao_id,
                    )
                    db.add(contrato)
                    stats["criados"] += 1

            except Exception as e:
                logger.error("ingestao.contrato.erro", pncp_id=pncp_id, erro=str(e))
                stats["erros"] += 1

        await db.commit()

    logger.info("ingestao.contratos.concluida", **stats)
    return stats


async def ingerir_tudo(
    data_inicial: date | None = None,
    data_final: date | None = None,
) -> dict:
    """Executa ingestão completa: contratações + contratos."""
    if not data_final:
        data_final = date.today()
    if not data_inicial:
        data_inicial = date(data_final.year - 1, 1, 1)

    logger.info(
        "ingestao.inicio",
        data_inicial=str(data_inicial),
        data_final=str(data_final),
    )

    stats_contratacoes = await ingerir_contratacoes(data_inicial, data_final)
    stats_contratos = await ingerir_contratos(data_inicial, data_final)

    return {
        "contratacoes": stats_contratacoes,
        "contratos": stats_contratos,
    }
