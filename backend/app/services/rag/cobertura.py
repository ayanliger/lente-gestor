"""Resumo estruturado de cobertura para perguntas sobre dados disponíveis."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag.recuperacao import DocumentoRelevante

_COBERTURA_DOC_ID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "lente-gestor:rag:cobertura-orcamento",
)

_TERMOS_COBERTURA = (
    "quais dados",
    "dados disponiveis",
    "dados disponíveis",
    "faltam dados",
    "falta dados",
    "falta dado",
    "cobertura",
    "base",
    "panorama completo",
    "outras funcoes",
    "outras funções",
    "disponibilidade",
    "ausente",
    "ausentes",
    "nao ha dados",
    "não há dados",
)


def pergunta_pede_cobertura(pergunta: str) -> bool:
    """Detecta perguntas sobre inventário/cobertura da base."""
    normalizada = _normalizar(pergunta)
    return any(_normalizar(termo) in normalizada for termo in _TERMOS_COBERTURA)


async def gerar_documento_cobertura(db: AsyncSession) -> DocumentoRelevante:
    """Gera um documento sintético com cobertura agregada do corpus RAG."""
    fontes = (await db.execute(text("""
        SELECT fonte, count(*) AS qtd
        FROM documentos_rag
        GROUP BY fonte
        ORDER BY fonte
    """))).all()

    resumo_funcao = (await db.execute(text("""
        SELECT
            count(*) AS docs,
            count(DISTINCT metadados->>'funcao') AS funcoes,
            count(
                DISTINCT ((metadados->>'exercicio') || '-B' || (metadados->>'periodo'))
            ) AS periodos,
            min((metadados->>'exercicio')::int) AS primeiro_ano,
            max((metadados->>'exercicio')::int) AS ultimo_ano
        FROM documentos_rag
        WHERE fonte = 'RESUMO_FUNCAO'
    """))).one()

    bimestres_por_ano = (await db.execute(text("""
        SELECT
            (metadados->>'exercicio')::int AS exercicio,
            string_agg(
                DISTINCT 'B' || (metadados->>'periodo'),
                ', '
                ORDER BY 'B' || (metadados->>'periodo')
            ) AS bimestres,
            count(DISTINCT metadados->>'funcao') AS funcoes
        FROM documentos_rag
        WHERE fonte = 'RESUMO_FUNCAO'
        GROUP BY 1
        ORDER BY 1
    """))).all()

    areas_finalisticas = (await db.execute(text("""
        SELECT
            metadados->>'funcao' AS funcao,
            count(*) AS docs,
            min((metadados->>'exercicio')::int || '/B' || (metadados->>'periodo')::int) AS primeiro,
            max((metadados->>'exercicio')::int || '/B' || (metadados->>'periodo')::int) AS ultimo
        FROM documentos_rag
        WHERE fonte = 'RESUMO_FUNCAO'
          AND (
            metadados->>'funcao' ILIKE '%Saúde%'
            OR metadados->>'funcao' ILIKE '%Educação%'
            OR metadados->>'funcao' ILIKE '%Assistência%'
            OR metadados->>'funcao' ILIKE '%Urbanismo%'
          )
        GROUP BY 1
        ORDER BY 1
    """))).all()

    fontes_texto = ", ".join(f"{row.fonte}: {row.qtd}" for row in fontes)
    anos_texto = "; ".join(
        f"{row.exercicio}: {row.bimestres} ({row.funcoes} funções)"
        for row in bimestres_por_ano
    )
    areas_texto = "; ".join(
        f"{row.funcao}: {row.docs} docs, {row.primeiro} a {row.ultimo}"
        for row in areas_finalisticas
    )

    conteudo = "\n".join(
        [
            "Cobertura agregada da base RAG e orçamentária disponível.",
            f"Documentos por fonte: {fontes_texto or 'sem documentos indexados'}.",
            (
                "Execução por função (RESUMO_FUNCAO): "
                f"{resumo_funcao.docs} documentos, "
                f"{resumo_funcao.funcoes} funções/subfunções distintas, "
                f"{resumo_funcao.periodos} combinações exercício/bimestre, "
                f"de {resumo_funcao.primeiro_ano} a {resumo_funcao.ultimo_ano}."
            ),
            f"Bimestres disponíveis por exercício em RESUMO_FUNCAO: {anos_texto}.",
            (
                "Áreas finalísticas presentes em RESUMO_FUNCAO: "
                f"{areas_texto or 'nenhuma das áreas consultadas foi encontrada'}."
            ),
            (
                "Use este resumo para afirmações sobre quais dados existem ou "
                "faltam na base. A ausência de um item em outros documentos "
                "recuperados não prova ausência na base completa."
            ),
        ]
    )

    metadados: dict[str, Any] = {
        "fontes": {row.fonte: row.qtd for row in fontes},
        "resumo_funcao_docs": resumo_funcao.docs,
        "resumo_funcao_funcoes": resumo_funcao.funcoes,
        "resumo_funcao_periodos": resumo_funcao.periodos,
        "primeiro_ano": resumo_funcao.primeiro_ano,
        "ultimo_ano": resumo_funcao.ultimo_ano,
    }

    return DocumentoRelevante(
        doc_id=_COBERTURA_DOC_ID,
        fonte="COBERTURA_DADOS",
        referencia_tipo="cobertura_dados",
        referencia_id=None,
        chave_unica="cobertura:orcamento",
        titulo="Cobertura dos dados disponíveis — orçamento e RAG",
        conteudo_texto=conteudo,
        metadados=metadados,
        score=1.0,
    )


def _normalizar(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acentos if not unicodedata.combining(c)).lower()
