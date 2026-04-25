"""
Serviço de derivação dos indicadores fiscais (LRF + mínimos constitucionais).

Lê células já ingeridas em `execucao_orcamentaria` (RGF e RREO) e popula
`indicadores_fiscais` com valor, limite legal e situação calculada.

Indicadores cobertos (11):

LRF — Despesa com Pessoal (Art. 19-22 + 59 §1º IV):
- DESPESA_PESSOAL_PCT_RCL        RGF-Anexo 06, limite 54% (Executivo)
- DESPESA_PESSOAL_PRUDENCIAL     derivado, limite 51,3% (95% do teto)
- LIMITE_ALERTA_PESSOAL          derivado, limite 48,6% (90% do teto)

LRF — Endividamento:
- DIVIDA_CONSOLIDADA_PCT_RCL     RGF-Anexo 06, limite 120%
- OP_CREDITO_PCT_RCL             RGF-Anexo 06, limite 16%
- GARANTIAS_PCT_RCL              RGF-Anexo 06, limite 22%

LRF — Equilíbrio orçamentário (Art. 4º, 9º e 42):
- RESULTADO_PRIMARIO             RREO-Anexo 06 (MONETARIO, piso 0)
- RESULTADO_NOMINAL              RREO-Anexo 06 (MONETARIO, piso 0)
- SUFICIENCIA_FINANCEIRA_RP      RGF-Anexo 06 (MONETARIO, piso 0 — Art. 42)

Mínimos Constitucionais:
- APLIC_MIN_SAUDE_PCT            RREO-Anexo 14, mínimo 15% (CF Art. 198)
- APLIC_MIN_EDUCACAO_PCT         RREO-Anexo 08, mínimo 25% (CF Art. 212)

Situação (ADR 10.3 — persistida, não derivada em consulta):
- OK: valor < 90% do limite máximo (ou valor ≥ piso mínimo)
- ALERTA: 90% ≤ valor < 100% do limite máximo
- EXCEDIDO: valor ≥ limite máximo
- ABAIXO_MINIMO: piso não atingido
- SEM_DADO: quando não há linha-fonte em execucao_orcamentaria

Indicadores MONETARIO com limite 0 (Resultado Primário/Nominal e
Suficiência de RP) usam a heurística simplificada valor ≥ 0 = OK,
valor < 0 = ABAIXO_MINIMO. Comparação com meta da LDO (caso do
primário/nominal) não é modelada hoje — o sinal do valor já resume
se o exercício fechou em superávit ou déficit, que é a leitura
gerencial mais direta. Art. 42 tem semântica estrita (disponibilidade
de caixa após inscrição em RP deve ser não-negativa).
"""

from dataclasses import dataclass
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import async_session
from app.models.contratacoes import Orgao
from app.models.orcamento import ExecucaoOrcamentaria, IndicadorFiscal

logger = structlog.get_logger()

# Situações
SIT_OK = "OK"
SIT_ALERTA = "ALERTA"
SIT_EXCEDIDO = "EXCEDIDO"
SIT_ABAIXO_MINIMO = "ABAIXO_MINIMO"
SIT_SEM_DADO = "SEM_DADO"

# Thresholds
FATOR_ALERTA = Decimal("0.90")  # 90% do limite máximo


@dataclass(frozen=True)
class DefinicaoIndicador:
    """
    Definição declarativa de um indicador: de onde vem, qual o limite,
    e qual a polaridade (teto máximo vs piso mínimo).
    """

    codigo: str
    descricao: str
    unidade: str  # PERCENTUAL ou MONETARIO
    limite_legal: Decimal
    tipo_limite: str  # "MAXIMO" (teto) ou "MINIMO" (piso)
    fonte_relatorio: str  # RGF ou RREO
    anexo: str
    cod_conta: str
    coluna: str
    conta: str | None = None  # filtro adicional opcional


# Mapeamento dos indicadores oficiais.
# Os cod_conta/coluna foram validados contra o payload real de Jequié 2024 Q2.
INDICADORES: list[DefinicaoIndicador] = [
    DefinicaoIndicador(
        codigo="DESPESA_PESSOAL_PCT_RCL",
        descricao="Despesa total com pessoal (% da RCL ajustada)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("54"),
        tipo_limite="MAXIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="DespesaTotalComPessoalDemonstrativoSimplificado",
        coluna="% SOBRE A RCL AJUSTADA",
    ),
    DefinicaoIndicador(
        codigo="DESPESA_PESSOAL_PRUDENCIAL",
        descricao="Despesa com pessoal x limite prudencial (% da RCL ajustada)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("51.3"),
        tipo_limite="MAXIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="DespesaTotalComPessoalDemonstrativoSimplificado",
        coluna="% SOBRE A RCL AJUSTADA",
    ),
    DefinicaoIndicador(
        codigo="LIMITE_ALERTA_PESSOAL",
        descricao="Despesa com pessoal x limite de alerta (% da RCL ajustada)",
        unidade="PERCENTUAL",
        # LRF Art. 59 §1º IV: 90% do teto do art. 20 (54% * 0,9 = 48,6%).
        limite_legal=Decimal("48.6"),
        tipo_limite="MAXIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="DespesaTotalComPessoalDemonstrativoSimplificado",
        coluna="% SOBRE A RCL AJUSTADA",
    ),
    DefinicaoIndicador(
        codigo="DIVIDA_CONSOLIDADA_PCT_RCL",
        descricao="Dívida consolidada líquida (% da RCL ajustada)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("120"),
        tipo_limite="MAXIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="DividaConsolidadaLiquidaDemonstrativoSimplificado",
        coluna="% SOBRE A RCL AJUSTADA",
    ),
    DefinicaoIndicador(
        codigo="OP_CREDITO_PCT_RCL",
        descricao="Operações de crédito internas e externas (% da RCL ajustada)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("16"),
        tipo_limite="MAXIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="OperacoesDeCreditoInternasEExternasDemonstrativoSimplificado",
        coluna="% SOBRE A RCL AJUSTADA",
    ),
    DefinicaoIndicador(
        codigo="GARANTIAS_PCT_RCL",
        descricao="Garantias concedidas (% da RCL ajustada)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("22"),
        tipo_limite="MAXIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="GarantiasDemonstrativoSimplificado",
        coluna="% SOBRE A RCL AJUSTADA",
    ),
    DefinicaoIndicador(
        codigo="APLIC_MIN_SAUDE_PCT",
        descricao="Aplicação mínima em Saúde (CF Art. 198 §2º)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("15"),
        tipo_limite="MINIMO",
        fonte_relatorio="RREO",
        anexo="RREO-Anexo 14",
        cod_conta="AplicacaoTotalDasDespesasComAcoesEServicosPublicosDeSaude",
        coluna="% Aplicado Até o Bimestre",
    ),
    DefinicaoIndicador(
        codigo="APLIC_MIN_EDUCACAO_PCT",
        descricao="Aplicação mínima em Educação (CF Art. 212)",
        unidade="PERCENTUAL",
        limite_legal=Decimal("25"),
        tipo_limite="MINIMO",
        fonte_relatorio="RREO",
        anexo="RREO-Anexo 08",
        cod_conta="AplicacaoTotalNoMinimoExigidoMDE",
        coluna="% Aplicado Até o Bimestre",
    ),
    # Equilíbrio fiscal (Art. 4º/9º LRF) — superávit ≥ 0 = OK, déficit = ABAIXO_MINIMO.
    # LDO pode fixar meta negativa; a comparação com meta está fora de escopo
    # no modelo atual (vide docstring do módulo).
    DefinicaoIndicador(
        codigo="RESULTADO_PRIMARIO",
        descricao="Resultado primário (sem RPPS — acima da linha)",
        unidade="MONETARIO",
        limite_legal=Decimal("0"),
        tipo_limite="MINIMO",
        fonte_relatorio="RREO",
        anexo="RREO-Anexo 06",
        cod_conta="ResultadoPrimarioSemRPPSAcimaDaLinha",
        coluna="VALOR",
    ),
    DefinicaoIndicador(
        codigo="RESULTADO_NOMINAL",
        descricao="Resultado nominal (sem RPPS — abaixo da linha)",
        unidade="MONETARIO",
        limite_legal=Decimal("0"),
        tipo_limite="MINIMO",
        fonte_relatorio="RREO",
        anexo="RREO-Anexo 06",
        cod_conta="ResultadoNominalAbaixoDaLinhaSemRPPS",
        coluna="VALOR",
    ),
    # Art. 42 LRF — no último quadrimestre do mandato, disponibilidade de
    # caixa líquida após inscrição em RP não processados não pode ser
    # negativa. Fora do último ano, segue sendo um bom indicador de
    # higiene fiscal.
    DefinicaoIndicador(
        codigo="SUFICIENCIA_FINANCEIRA_RP",
        descricao="Suficiência financeira para Restos a Pagar (Art. 42 LRF)",
        unidade="MONETARIO",
        limite_legal=Decimal("0"),
        tipo_limite="MINIMO",
        fonte_relatorio="RGF",
        anexo="RGF-Anexo 06",
        cod_conta="ValorTotalRestosAPagarDemonstrativoSimplificado",
        coluna=(
            "DISPONIBILIDADE DE CAIXA LÍQUIDA (APÓS A INSCRIÇÃO EM "
            "RESTOS A PAGAR NÃO PROCESSADOS DO EXERCÍCIO)"
        ),
    ),
]


def _derivar_situacao(
    valor: Decimal | None, limite: Decimal, tipo_limite: str
) -> str:
    """
    Regras de situação:
    - SEM_DADO se valor ausente
    - MAXIMO (teto): OK < 90%, ALERTA 90-100%, EXCEDIDO ≥ limite
    - MINIMO (piso): OK se valor ≥ limite, ABAIXO_MINIMO caso contrário
    """
    if valor is None:
        return SIT_SEM_DADO

    if tipo_limite == "MAXIMO":
        if valor >= limite:
            return SIT_EXCEDIDO
        if valor >= limite * FATOR_ALERTA:
            return SIT_ALERTA
        return SIT_OK

    if tipo_limite == "MINIMO":
        if valor >= limite:
            return SIT_OK
        return SIT_ABAIXO_MINIMO

    raise ValueError(f"tipo_limite inválido: {tipo_limite}")


async def _buscar_linha_fonte(
    db: AsyncSession,
    *,
    orgao_id,
    exercicio: int,
    definicao: DefinicaoIndicador,
) -> ExecucaoOrcamentaria | None:
    """
    Busca a linha mais recente (maior período) em execucao_orcamentaria
    que casa com a definição do indicador no exercício dado.
    """
    query = (
        select(ExecucaoOrcamentaria)
        .where(
            ExecucaoOrcamentaria.orgao_id == orgao_id,
            ExecucaoOrcamentaria.exercicio == exercicio,
            ExecucaoOrcamentaria.tipo_relatorio == definicao.fonte_relatorio,
            ExecucaoOrcamentaria.anexo == definicao.anexo,
            ExecucaoOrcamentaria.cod_conta == definicao.cod_conta,
            ExecucaoOrcamentaria.coluna == definicao.coluna,
        )
        .order_by(ExecucaoOrcamentaria.periodo.desc().nullslast())
        .limit(1)
    )
    if definicao.conta:
        query = query.where(ExecucaoOrcamentaria.conta == definicao.conta)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def derivar_indicadores_fiscais(
    exercicio: int,
    orgao_cnpj: str | None = None,
) -> dict:
    """
    Calcula/atualiza todos os indicadores LRF+mínimos para um exercício.

    Para cada indicador em `INDICADORES`, busca a linha-fonte mais
    recente em `execucao_orcamentaria` e faz upsert em `indicadores_fiscais`.
    Indicadores sem fonte ficam com situacao=SEM_DADO.

    Retorna: {criados, atualizados, sem_dado, total_indicadores}.
    """
    cnpj = orgao_cnpj or get_settings().pncp_cnpj_jequie
    stats = {
        "criados": 0,
        "atualizados": 0,
        "sem_dado": 0,
        "total_indicadores": 0,
    }

    async with async_session() as db:
        result = await db.execute(select(Orgao).where(Orgao.cnpj == cnpj))
        orgao = result.scalar_one_or_none()
        if orgao is None:
            logger.warning("indicadores.orgao_nao_encontrado", cnpj=cnpj)
            return stats

        for definicao in INDICADORES:
            stats["total_indicadores"] += 1

            fonte = await _buscar_linha_fonte(
                db,
                orgao_id=orgao.id,
                exercicio=exercicio,
                definicao=definicao,
            )

            valor = fonte.valor if fonte else None
            situacao = _derivar_situacao(
                valor, definicao.limite_legal, definicao.tipo_limite
            )

            if situacao == SIT_SEM_DADO:
                stats["sem_dado"] += 1

            # Upsert
            result = await db.execute(
                select(IndicadorFiscal).where(
                    IndicadorFiscal.orgao_id == orgao.id,
                    IndicadorFiscal.exercicio == exercicio,
                    IndicadorFiscal.periodo == (fonte.periodo if fonte else None),
                    IndicadorFiscal.codigo == definicao.codigo,
                )
            )
            existing = result.scalar_one_or_none()

            campos = {
                "exercicio": exercicio,
                "periodo": fonte.periodo if fonte else None,
                "codigo": definicao.codigo,
                "descricao": definicao.descricao,
                "unidade": definicao.unidade,
                "valor": valor,
                "limite_legal": definicao.limite_legal,
                "situacao": situacao,
                "fonte_relatorio": definicao.fonte_relatorio,
                "fonte_exercicio": fonte.exercicio if fonte else None,
                "fonte_periodo": fonte.periodo if fonte else None,
            }

            if existing:
                for k, v in campos.items():
                    setattr(existing, k, v)
                existing.orgao_id = orgao.id
                stats["atualizados"] += 1
            else:
                registro = IndicadorFiscal(**campos, orgao_id=orgao.id)
                db.add(registro)
                stats["criados"] += 1

            logger.info(
                "indicadores.derivado",
                codigo=definicao.codigo,
                valor=str(valor) if valor is not None else None,
                situacao=situacao,
            )

        await db.commit()

    logger.info("indicadores.concluido", exercicio=exercicio, **stats)
    return stats
