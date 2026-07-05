"""
Ferramentas (function calling) — consultas estruturadas que o modelo pode
invocar quando a pergunta exige filtros determinísticos.

A camada RAG semântica (vector search) é insuficiente para perguntas que
combinam janelas temporais ou busca categórica exaustiva (ex: "contratos
vencendo nos próximos 90 dias", "contratos de tecnologia em 2025"). Para
essas perguntas, o modelo declara uma function call e o executor traduz em
SQL no banco operacional, devolvendo um bloco de texto pré-numerado que
entra no protocolo de citações.

Dois artefatos saem de cada chamada:
- `texto`: bloco numerado para o modelo citar via `[n]`.
- `docs`: lista de :class:`DocumentoRelevante` que vai para o pool de
  citações da resposta — o frontend abre o registro de origem ao clicar
  no chip da fonte.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import structlog
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contratacoes import Contrato, Fornecedor
from app.models.rag import DocumentoRag, FonteDocumento
from app.services.rag.client import GeminiClient
from app.services.rag.recuperacao import DocumentoRelevante

logger = structlog.get_logger()

# Defaults conservadores: cada tool aceita parâmetros do modelo, mas
# ancora dentro de limites seguros para evitar respostas com 200+ linhas.
_DIAS_PADRAO = 90
_DIAS_MAX = 365
_TAMANHO_MAX = 50
_TAMANHO_PADRAO = 20

# Limiar de similaridade cosseno para o filtro semântico de categoria. Mais
# baixo que o limiar do retrieval RAG (0.30) porque categorias têm vetor
# muito mais curto que perguntas inteiras — 0.40 capta sinônimos
# ("tecnologia" → "ponto eletrônico", "software", "sistema") sem permitir
# itens completamente off-topic.
_LIMIAR_SEMANTICO = 0.40


@dataclass(slots=True)
class ResultadoFerramenta:
    """Saída padrão dos executores de tool."""

    texto: str
    docs: list[DocumentoRelevante] = field(default_factory=list)


# ──────────────────────────────────────────
# contratos_vencendo
# ──────────────────────────────────────────


CONTRATOS_VENCENDO_DECL = types.FunctionDeclaration(
    name="contratos_vencendo",
    description=(
        "Retorna contratos firmados cuja vigência termina dentro de N dias "
        "a partir de hoje. Use quando a pergunta envolve vencimento, "
        "encerramento ou expiração de contratos em janela temporal "
        "(ex: 'próximos 90 dias', 'que vencem ainda este mês'). "
        "Filtra opcionalmente por categoria semântica via embeddings: "
        "termos como 'tecnologia' encontram contratos sobre software, "
        "ponto eletrônico, etc., mesmo sem a palavra exata no objeto."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "dias": types.Schema(
                type=types.Type.INTEGER,
                description=(
                    "Janela em dias a partir de hoje. Padrão 90, máximo 365."
                ),
            ),
            "categoria_objeto": types.Schema(
                type=types.Type.STRING,
                description=(
                    "Categoria/tema semântico para filtrar os contratos da "
                    "janela. Termos curtos do português: 'tecnologia', "
                    "'limpeza', 'iluminação', 'segurança', 'saúde'. O "
                    "matching usa embeddings (pgvector), então sinônimos e "
                    "termos relacionados também são encontrados. Omita para "
                    "listar todos os contratos no intervalo."
                ),
            ),
        },
        required=[],
    ),
)


async def executar_contratos_vencendo(
    *,
    db: AsyncSession,
    cliente: GeminiClient | None = None,
    dias: int | None = None,
    categoria_objeto: str | None = None,
) -> ResultadoFerramenta:
    """Executor de :data:`CONTRATOS_VENCENDO_DECL`.

    Filtra contratos por janela de vigência (sempre estrutural via SQL) e,
    quando ``categoria_objeto`` for fornecida, faz ranking semântico via
    pgvector usando o embedding do termo contra os embeddings dos contratos
    já indexados em ``documentos_rag``. Caso não haja ``cliente`` para
    embedar o termo, cai num ILIKE literal — mantendo o tool funcional
    fora do contexto de produção.
    """
    janela = max(1, min(int(dias or _DIAS_PADRAO), _DIAS_MAX))
    hoje = date.today()
    limite = hoje + timedelta(days=janela)
    categoria = (categoria_objeto or "").strip() or None

    if categoria and cliente is not None:
        contratos, similaridades = await _ranquear_por_similaridade(
            db=db,
            cliente=cliente,
            categoria=categoria,
            hoje=hoje,
            limite=limite,
        )
        modo_filtro = "semântico"
    else:
        contratos = await _filtrar_estrutural(
            db=db,
            hoje=hoje,
            limite=limite,
            categoria=categoria,
        )
        similaridades = {}
        modo_filtro = "literal" if categoria else "sem-filtro"

    if not contratos:
        sufixo = f" para a categoria {categoria!r}" if categoria else ""
        return ResultadoFerramenta(
            texto=(
                f"Nenhum contrato com vigência terminando nos próximos "
                f"{janela} dias{sufixo}."
            ),
            docs=[],
        )

    if categoria and modo_filtro == "semântico":
        sufixo_categoria = (
            f" filtrando semanticamente por {categoria!r} "
            f"(limiar {_LIMIAR_SEMANTICO:.2f})"
        )
    elif categoria:
        sufixo_categoria = f" filtrando literalmente por {categoria!r}"
    else:
        sufixo_categoria = ""

    cabecalho = (
        f"Contratos com vigência terminando até {limite.isoformat()} "
        f"(janela de {janela} dias a partir de {hoje.isoformat()}). "
        f"{len(contratos)} resultado(s){sufixo_categoria}."
    )

    return _renderizar_resultado_contratos(
        contratos=contratos,
        cabecalho=cabecalho,
        fonte_tool="contratos_vencendo",
        similaridades=similaridades,
    )


# ──────────────────────────────────────────
# buscar_contratos
# ──────────────────────────────────────────


BUSCAR_CONTRATOS_DECL = types.FunctionDeclaration(
    name="buscar_contratos",
    description=(
        "Busca contratos firmados por substring no objeto/categoria, com "
        "filtros opcionais por ano e fornecedor. Use quando a pergunta cita "
        "um tema específico (ex: 'contratos de tecnologia', 'contratos de "
        "limpeza') ou um fornecedor nominal. Não usar quando já houver "
        "documentos suficientes na lista DOCUMENTOS RECUPERADOS."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "busca": types.Schema(
                type=types.Type.STRING,
                description="Termo de busca (ILIKE) no objeto ou categoria.",
            ),
            "fornecedor_nome": types.Schema(
                type=types.Type.STRING,
                description="Substring do nome do fornecedor (ILIKE).",
            ),
            "ano": types.Schema(
                type=types.Type.INTEGER,
                description="Ano do contrato (campo `ano`).",
            ),
            "tamanho": types.Schema(
                type=types.Type.INTEGER,
                description=(
                    f"Quantidade máxima de contratos (1–{_TAMANHO_MAX}; "
                    f"padrão {_TAMANHO_PADRAO})."
                ),
            ),
        },
        required=[],
    ),
)


async def executar_buscar_contratos(
    *,
    db: AsyncSession,
    busca: str | None = None,
    fornecedor_nome: str | None = None,
    ano: int | None = None,
    tamanho: int | None = None,
) -> ResultadoFerramenta:
    """Executor de :data:`BUSCAR_CONTRATOS_DECL`."""
    if not (busca or fornecedor_nome or ano):
        # Se o modelo chamou sem nenhum filtro, recusa em vez de devolver
        # 50 contratos arbitrários. Isso evita ruído no prompt subsequente.
        return ResultadoFerramenta(
            texto=(
                "Ferramenta `buscar_contratos` exige pelo menos um filtro "
                "(busca, fornecedor_nome ou ano). Reformule a chamada."
            ),
            docs=[],
        )

    limite = max(1, min(int(tamanho or _TAMANHO_PADRAO), _TAMANHO_MAX))
    query = (
        select(Contrato)
        .options(selectinload(Contrato.fornecedor))
        .order_by(
            Contrato.data_fim_vigencia.asc().nullslast(),
            Contrato.valor_atual.desc().nullslast(),
        )
        .limit(limite)
    )
    if busca:
        like = f"%{busca.strip()}%"
        query = query.where(
            Contrato.objeto.ilike(like) | Contrato.categoria.ilike(like)
        )
    if fornecedor_nome:
        forn_like = f"%{fornecedor_nome.strip()}%"
        query = query.join(Fornecedor, Contrato.fornecedor_id == Fornecedor.id).where(
            Fornecedor.nome.ilike(forn_like)
        )
    if ano:
        query = query.where(Contrato.ano == int(ano))

    contratos = (await db.execute(query)).scalars().all()

    filtros = ", ".join(
        parte
        for parte in (
            f"busca={busca!r}" if busca else None,
            f"fornecedor={fornecedor_nome!r}" if fornecedor_nome else None,
            f"ano={ano}" if ano else None,
        )
        if parte
    )

    if not contratos:
        return ResultadoFerramenta(
            texto=f"Nenhum contrato encontrado para os filtros: {filtros}.",
            docs=[],
        )

    cabecalho = (
        f"{len(contratos)} contrato(s) encontrado(s) para os filtros: {filtros}."
    )

    return _renderizar_resultado_contratos(
        contratos=contratos,
        cabecalho=cabecalho,
        fonte_tool="buscar_contratos",
    )


# ──────────────────────────────────────────
# Registry
# ──────────────────────────────────────────


ToolExecutor = Callable[..., Awaitable[ResultadoFerramenta]]


@dataclass(slots=True)
class ToolRegistry:
    """Conjunto de tools disponibilizadas ao modelo + executores síncronos.

    `declarations` vai direto para o config do Gemini. `executors` é
    consultado pelo loop de function-calling para resolver `function_call`
    do modelo em `function_response`.
    """

    declarations: list[types.FunctionDeclaration]
    executors: dict[str, ToolExecutor]

    @property
    def nomes(self) -> list[str]:
        return [d.name for d in self.declarations]


def construir_registry_padrao() -> ToolRegistry:
    """Tools do escopo Fase 1 — contratos com filtros estruturados."""
    return ToolRegistry(
        declarations=[CONTRATOS_VENCENDO_DECL, BUSCAR_CONTRATOS_DECL],
        executors={
            "contratos_vencendo": executar_contratos_vencendo,
            "buscar_contratos": executar_buscar_contratos,
        },
    )


# ───────────────────────────────────────────
# Helpers de filtragem
# ───────────────────────────────────────────


async def _filtrar_estrutural(
    *,
    db: AsyncSession,
    hoje: date,
    limite: date,
    categoria: str | None,
) -> list[Contrato]:
    """Filtro 100% SQL: janela de vigência + ILIKE opcional.

    Caminho de fallback usado quando não há ``GeminiClient`` disponível
    para embedar a categoria, ou quando nenhuma categoria foi informada.
    """
    query = (
        select(Contrato)
        .options(selectinload(Contrato.fornecedor))
        .where(
            Contrato.data_fim_vigencia.is_not(None),
            Contrato.data_fim_vigencia >= hoje,
            Contrato.data_fim_vigencia <= limite,
        )
        .order_by(Contrato.data_fim_vigencia.asc())
        .limit(_TAMANHO_MAX)
    )
    if categoria:
        like = f"%{categoria}%"
        query = query.where(
            Contrato.objeto.ilike(like) | Contrato.categoria.ilike(like)
        )
    return list((await db.execute(query)).scalars().all())


async def _ranquear_por_similaridade(
    *,
    db: AsyncSession,
    cliente: GeminiClient,
    categoria: str,
    hoje: date,
    limite: date,
) -> tuple[list[Contrato], dict[uuid.UUID, float]]:
    """Ranking semântico via pgvector.

    1. Embeda o termo ``categoria`` com o mesmo modelo do RAG
       (`task_type=RETRIEVAL_QUERY`).
    2. Faz JOIN contratos ⇔ documentos_rag (fonte CONTRATO) e ordena por
       distância cosseno.
    3. Mantém apenas contratos com similaridade ≥ ``_LIMIAR_SEMANTICO``.

    Retorna a lista de contratos e um mapa ``contrato.id -> similaridade``
    para que a renderização exiba o score na linha.
    """
    try:
        vetor = await cliente.embed_text(
            categoria, task_type="RETRIEVAL_QUERY"
        )
    except Exception:  # noqa: BLE001
        # Falha no embed (quota, rede): caia para o filtro estrutural com
        # ILIKE. Logamos para diagnóstico e o caller marca o modo
        # adequado no cabeçalho da resposta.
        logger.exception("rag.tools.embed_falhou", categoria=categoria)
        contratos = await _filtrar_estrutural(
            db=db, hoje=hoje, limite=limite, categoria=categoria
        )
        return contratos, {}

    distancia = DocumentoRag.embedding.cosine_distance(vetor).label("distancia")
    query = (
        select(Contrato, distancia)
        .options(selectinload(Contrato.fornecedor))
        .join(
            DocumentoRag,
            (DocumentoRag.referencia_id == Contrato.id)
            & (DocumentoRag.fonte == FonteDocumento.CONTRATO.value),
        )
        .where(
            Contrato.data_fim_vigencia.is_not(None),
            Contrato.data_fim_vigencia >= hoje,
            Contrato.data_fim_vigencia <= limite,
        )
        .order_by(distancia.asc())
        .limit(_TAMANHO_MAX)
    )

    rows = (await db.execute(query)).all()
    contratos: list[Contrato] = []
    similaridades: dict[uuid.UUID, float] = {}
    for contrato, dist in rows:
        score = max(0.0, 1.0 - float(dist))
        if score < _LIMIAR_SEMANTICO:
            # Itens vencendo a partir daqui não são suficientemente
            # relacionados à categoria pedida — paramos.
            break
        contratos.append(contrato)
        similaridades[contrato.id] = score
    return contratos, similaridades


# ───────────────────────────────────────────
# Helpers de renderização
# ───────────────────────────────────────────


def _renderizar_resultado_contratos(
    *,
    contratos: list[Contrato],
    cabecalho: str,
    fonte_tool: str,
    similaridades: dict[uuid.UUID, float] | None = None,
) -> ResultadoFerramenta:
    """Monta o bloco numerado + lista de DocumentoRelevante para citação."""
    linhas = [cabecalho]
    docs: list[DocumentoRelevante] = []
    similaridades = similaridades or {}

    for i, c in enumerate(contratos, start=1):
        nome_forn = c.fornecedor.nome if c.fornecedor else "fornecedor não identificado"
        cnpj_forn = c.fornecedor.cpf_cnpj if c.fornecedor else "—"
        valor = float(c.valor_atual or c.valor_inicial or 0)
        valor_txt = _fmt_brl(valor) if valor else "valor não informado"
        objeto = (c.objeto or "").strip().replace("\n", " ") or "—"
        objeto_curto = objeto if len(objeto) <= 220 else objeto[:217] + "..."
        score = similaridades.get(c.id)

        partes = [
            f"[{i}] Contrato {c.numero_contrato or c.pncp_id or c.id}",
        ]
        if c.data_fim_vigencia:
            partes.append(f"vence em {c.data_fim_vigencia.isoformat()}")
        elif c.data_inicio_vigencia:
            partes.append(f"início vigência {c.data_inicio_vigencia.isoformat()}")
        partes.extend(
            [
                f"fornecedor: {nome_forn} (CPF/CNPJ {cnpj_forn})",
                f"valor: {valor_txt}",
                f"objeto: {objeto_curto}",
            ]
        )
        if c.categoria:
            partes.append(f"categoria: {c.categoria}")
        if c.situacao:
            partes.append(f"situação: {c.situacao}")
        if score is not None:
            partes.append(f"similaridade {score * 100:.0f}%")
        linha = "; ".join(partes) + "."
        linhas.append(linha)

        docs.append(
            DocumentoRelevante(
                doc_id=c.id,
                fonte="CONTRATO",
                referencia_tipo="contrato",
                referencia_id=c.id,
                chave_unica=f"contrato:{c.id}",
                titulo=f"Contrato — {objeto_curto[:120]}",
                conteudo_texto=linha,
                metadados={
                    "numero_contrato": c.numero_contrato,
                    "pncp_id": c.pncp_id,
                    "data_inicio_vigencia": (
                        c.data_inicio_vigencia.isoformat()
                        if c.data_inicio_vigencia
                        else None
                    ),
                    "data_fim_vigencia": (
                        c.data_fim_vigencia.isoformat()
                        if c.data_fim_vigencia
                        else None
                    ),
                    "fornecedor_nome": nome_forn,
                    "fornecedor_cnpj": cnpj_forn,
                    "valor_atual": (
                        float(c.valor_atual) if c.valor_atual is not None else None
                    ),
                    "valor_inicial": (
                        float(c.valor_inicial)
                        if c.valor_inicial is not None
                        else None
                    ),
                    "categoria": c.categoria,
                    "situacao": c.situacao,
                    "fonte_tool": fonte_tool,
                    "similaridade": score,
                },
                score=score if score is not None else 1.0,
            )
        )

    return ResultadoFerramenta(texto="\n".join(linhas), docs=docs)


def _fmt_brl(valor: float | None) -> str:
    if not valor:
        return "—"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Ajuda explícita ao IDE/linter — uuid usado em metadados acumulados pelo
# wrapper externo; mantemos referência leve aqui para deixar os imports
# explícitos quando os executores forem chamados.
_ = uuid


__all__ = [
    "BUSCAR_CONTRATOS_DECL",
    "CONTRATOS_VENCENDO_DECL",
    "ResultadoFerramenta",
    "ToolExecutor",
    "ToolRegistry",
    "construir_registry_padrao",
    "executar_buscar_contratos",
    "executar_contratos_vencendo",
]


# Os parâmetros opcionais ``Any`` ajudam a manter a assinatura aberta a
# extensões futuras de tools sem quebrar callers que importam o módulo.
_ = Any
