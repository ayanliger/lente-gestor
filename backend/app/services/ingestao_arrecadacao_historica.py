"""
Backfill histórico de arrecadação via SICONFI DCA (Demonstrativo Contábil Anual).

Contexto: o portal Município Online não republicou arrecadação realizada para
exercícios 2020–2022 (apenas linhas de previsão com valor zerado). O DCA do
Tesouro Nacional (Anexo I-C — Balanço Orçamentário) traz a `Receita Bruta
Realizada` anual por `cod_conta` do STN, cobrindo exatamente esse gap.

Este serviço lê o DCA via SICONFI, filtra as folhas da hierarquia de natureza
de receita (evita somar rollups que já incluem seus filhos) e grava cada folha
em `arrecadacao` com:

- `mes = 12` (sentinela anual — DCA não tem granularidade mensal);
- `fonte = "SICONFI_DCA"` e `cod_fonte_recurso = "SICONFI_DCA"` (isola as linhas
  sintéticas das reais do Município Online via `cod_fonte_recurso` no índice
  único e via `fonte` nos filtros de endpoints mensais).

Cobertura validada em 04/2026 (Jequié): 2020 → R$ 469 mi, 2021 → R$ 495 mi,
2022 → R$ 649 mi. Sem conflito com dados 2023+ do Município Online porque os
anos são disjuntos.
"""

import json
from decimal import Decimal, InvalidOperation

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors.siconfi import SICONFIClient
from app.db.session import async_session
from app.models.arrecadacao import Arrecadacao
from app.models.contratacoes import Orgao

logger = structlog.get_logger()
settings = get_settings()

FONTE_DCA = "SICONFI_DCA"
COD_FONTE_DCA = "SICONFI_DCA"
ANEXO_PADRAO = "DCA-Anexo I-C"
COLUNA_RECEITA_REALIZADA = "Receitas Brutas Realizadas"
# Em DCA Anexo I-C, apenas `cod_conta` com prefixo `RO` ("Receita Orçamentária")
# traz valores de arrecadação. Demais prefixos são chaves simbólicas (ex.:
# `ReceitasExcetoIntraOrcamentarias`, `SubtotalDasReceitas`) ou despesas.
PREFIXO_RECEITA = "RO"
# DCA é anual — usamos dezembro como sentinela para caber no shape mês/ano da
# tabela `arrecadacao`, que é mensal por construção.
MES_SENTINELA = 12


# ──────────────────────────────────────────
# Parse e hierarquia STN
# ──────────────────────────────────────────


def _parse_decimal(value: object) -> Decimal | None:
    """Converte número/string DCA para Decimal; retorna None se inválido."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _partes(cod_conta: str) -> list[str]:
    """Retorna os 7 grupos numéricos do cod_conta do STN (tira o prefixo `RO`)."""
    sem_prefixo = (
        cod_conta[len(PREFIXO_RECEITA) :]
        if cod_conta.startswith(PREFIXO_RECEITA)
        else cod_conta
    )
    return sem_prefixo.split(".")


def _profundidade_stn(cod_conta: str) -> int:
    """
    Profundidade de um cod_conta na hierarquia STN (1 a 7).

    A hierarquia STN tem 7 grupos:
        Categoria.Origem.Espécie.Rubrica.Alínea(2d).Sub-alínea.Detalhamento

    Zero-trailing indica agregação: `1.1.1.0.00.0.0` é o nível 3 (Espécie)
    e agrega todos os filhos em nível 4+. A profundidade é o último índice
    onde o grupo não é só zeros.
    """
    partes = _partes(cod_conta)
    for i in range(len(partes) - 1, -1, -1):
        if partes[i].strip("0"):
            return i + 1
    return 0


def _eh_ancestral(candidato_pai: str, candidato_filho: str) -> bool:
    """
    True se `candidato_pai` é ancestral estrito de `candidato_filho` na
    hierarquia STN (mesma raiz até a profundidade do pai, profundidade menor).

    Necessário porque o DCA devolve todos os níveis da hierarquia em uma
    única lista achatada, e somar todos resultaria em N-contagem dos
    valores dos nós-filhos.
    """
    pais = _partes(candidato_pai)
    filhos = _partes(candidato_filho)
    if len(pais) != len(filhos):
        return False
    prof_pai = _profundidade_stn(candidato_pai)
    prof_filho = _profundidade_stn(candidato_filho)
    if prof_pai >= prof_filho:
        return False
    return all(pais[i] == filhos[i] for i in range(prof_pai))


def _folhas_stn(items: list[dict]) -> list[dict]:
    """
    Filtra a lista para manter apenas as folhas verdadeiras da hierarquia.

    Uma linha é folha se nenhuma outra linha do conjunto é sua descendente
    no STN. A soma das folhas reproduz o total da raiz da hierarquia sem
    dupla contagem.
    """
    codigos = {i["cod_conta"] for i in items if i.get("cod_conta")}
    return [
        i
        for i in items
        if not any(
            _eh_ancestral(i["cod_conta"], outro)
            for outro in codigos
            if outro != i["cod_conta"]
        )
    ]


def _cod_item_receita_from_dca(cod_conta: str) -> str:
    """
    Converte `cod_conta` DCA (`RO1.1.1.8.01.1.0`) para um código STN flat
    de 12 dígitos (`111801010000`) compatível com `arrecadacao.cod_item_receita`.

    Estratégia: remove o prefixo `RO` e os pontos, preserva a largura de
    cada grupo STN (1, 1, 1, 1, 2, 1, 1 = 8 dígitos da natureza de receita)
    e preenche até 12 com zeros à direita para espelhar o padrão que o
    Município Online usa (12 dígitos = 8 de natureza + 4 de detalhamento).
    """
    sem_prefixo = cod_conta.removeprefix(PREFIXO_RECEITA)
    plano = "".join(sem_prefixo.split("."))
    return plano.ljust(12, "0")[:12]


# ──────────────────────────────────────────
# Normalização e upsert
# ──────────────────────────────────────────


def _normalizar_dca(raw: dict, exercicio: int) -> dict:
    """Mapeia um item DCA (folha) para os campos do modelo Arrecadacao."""
    cod_conta = raw.get("cod_conta") or ""
    conta = (raw.get("conta") or "").strip()
    # `conta` vem do DCA prefixado com o próprio cod_conta (ex.:
    # `"1.1.1.8.01.1.0 - Imposto sobre a Propriedade..."`). Remover o prefixo
    # para deixar só a descrição humana.
    descricao = conta
    prefixo_numerico = cod_conta.removeprefix(PREFIXO_RECEITA)
    if descricao.startswith(prefixo_numerico):
        descricao = descricao[len(prefixo_numerico) :].lstrip(" -").strip()

    return {
        "exercicio": exercicio,
        "mes": MES_SENTINELA,
        "data_emissao": None,
        "cod_item_receita": _cod_item_receita_from_dca(cod_conta),
        "descricao_receita": descricao[:500],
        "poder": None,
        "categoria": None,
        "cod_fonte_recurso": COD_FONTE_DCA,
        "descricao_fonte_recurso": f"SICONFI DCA {raw.get('anexo') or ANEXO_PADRAO}",
        "valor_previsto": None,
        "valor_atualizado": None,
        "valor_arrecadado_periodo": _parse_decimal(raw.get("valor")),
        "valor_arrecadado_acumulado": _parse_decimal(raw.get("valor")),
        "fonte": FONTE_DCA,
        "dados_brutos": json.dumps(raw, ensure_ascii=False, default=str),
    }


async def _upsert_orgao_from_siconfi(db: AsyncSession, raw: dict) -> Orgao:
    """
    Retorna ou cria o Orgao correspondente ao ente do SICONFI.

    Enriquece UF/município/esfera a partir do payload do DCA quando o
    Orgao já existir com campos vazios.
    """
    cnpj = settings.pncp_cnpj_jequie

    result = await db.execute(select(Orgao).where(Orgao.cnpj == cnpj))
    orgao = result.scalar_one_or_none()

    instituicao = (raw.get("instituicao") or "").strip()
    uf = raw.get("uf")
    municipio: str | None = None
    if " de " in instituicao and " - " in instituicao:
        municipio = instituicao.split(" de ", 1)[1].split(" - ", 1)[0].strip()

    if orgao:
        if not orgao.uf and uf:
            orgao.uf = uf
        if not orgao.municipio and municipio:
            orgao.municipio = municipio
        if not orgao.esfera:
            orgao.esfera = "M"
        return orgao

    orgao = Orgao(
        cnpj=cnpj,
        razao_social=instituicao or f"MUNICÍPIO {cnpj}",
        esfera="M",
        uf=uf,
        municipio=municipio,
    )
    db.add(orgao)
    await db.flush()
    logger.info(
        "ingestao.arrecadacao_historica.orgao_criado",
        cnpj=cnpj,
        razao=orgao.razao_social,
    )
    return orgao


async def _upsert_arrecadacao(
    db: AsyncSession, campos: dict, orgao_id, cod_ibge: str, stats: dict
) -> None:
    """
    Upsert pela chave única `(orgao_id, exercicio, mes, cod_item_receita,
    cod_fonte_recurso)`. Como `cod_fonte_recurso = "SICONFI_DCA"` é
    distinto dos valores reais do Município Online, linhas DCA nunca
    conflitam com linhas do portal mesmo quando um dia 2020–2022 passar
    a ter dados realizados lá.
    """
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
        stats["atualizados"] += 1
        return

    registro = Arrecadacao(**campos, orgao_id=orgao_id, cod_ibge=cod_ibge)
    db.add(registro)
    stats["criados"] += 1


# ──────────────────────────────────────────
# Pipeline público
# ──────────────────────────────────────────


async def ingerir_arrecadacao_dca(
    exercicios: list[int],
    no_anexo: str = ANEXO_PADRAO,
) -> dict:
    """
    Ingere a arrecadação anual via SICONFI DCA para os exercícios informados.

    Um exercício que falhar no fetch não interrompe os demais — o stat
    `erros` é incrementado e seguimos.

    Retorna: `{criados, atualizados, erros, exercicios_processados}`.
    """
    stats = {
        "criados": 0,
        "atualizados": 0,
        "erros": 0,
        "exercicios_processados": 0,
    }
    cod_ibge = settings.siconfi_id_ente_jequie

    async with SICONFIClient() as siconfi:
        for exercicio in exercicios:
            try:
                items = await siconfi.paginar_dca(
                    an_exercicio=exercicio, no_anexo=no_anexo
                )
            except Exception as e:
                logger.error(
                    "ingestao.arrecadacao_historica.fetch_erro",
                    exercicio=exercicio,
                    erro=str(e),
                )
                stats["erros"] += 1
                continue

            receitas = [
                i
                for i in items
                if i.get("coluna") == COLUNA_RECEITA_REALIZADA
                and (i.get("cod_conta") or "").startswith(PREFIXO_RECEITA)
            ]
            folhas = _folhas_stn(receitas)

            logger.info(
                "ingestao.arrecadacao_historica.folhas",
                exercicio=exercicio,
                total_items=len(items),
                total_receitas=len(receitas),
                total_folhas=len(folhas),
            )

            async with async_session() as db:
                orgao: Orgao | None = None

                for raw in folhas:
                    try:
                        if orgao is None:
                            orgao = await _upsert_orgao_from_siconfi(db, raw)

                        campos = _normalizar_dca(raw, exercicio)
                        if not campos["cod_item_receita"]:
                            continue
                        if campos["valor_arrecadado_periodo"] is None:
                            continue
                        if campos["valor_arrecadado_periodo"] == Decimal("0"):
                            # DCA frequentemente lista rubricas previstas mas
                            # não realizadas; pular para não inflar a tabela.
                            continue

                        await _upsert_arrecadacao(
                            db, campos, orgao.id, cod_ibge, stats
                        )
                    except Exception as e:
                        logger.error(
                            "ingestao.arrecadacao_historica.item_erro",
                            exercicio=exercicio,
                            cod_conta=raw.get("cod_conta"),
                            erro=str(e),
                        )
                        stats["erros"] += 1

                await db.commit()

            stats["exercicios_processados"] += 1
            logger.info(
                "ingestao.arrecadacao_historica.exercicio_concluido",
                exercicio=exercicio,
                folhas=len(folhas),
            )

    logger.info("ingestao.arrecadacao_historica.concluida", **stats)
    return stats
