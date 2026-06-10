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
from app.services.rag.recuperacao import DocumentoRelevante

logger = structlog.get_logger()

# Defaults conservadores: cada tool aceita parâmetros do modelo, mas
# ancora dentro de limites seguros para evitar respostas com 200+ linhas.
_DIAS_PADRAO = 90
_DIAS_MAX = 365
_TAMANHO_MAX = 50
_TAMANHO_PADRAO = 20


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
        "Filtra opcionalmente por substring no objeto/categoria do contrato."
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
                    "Substring opcional para filtrar pelo objeto ou categoria "
                    "do contrato (ILIKE). Use termos do português comum: "
                    "'tecnologia', 'limpeza', 'iluminação', 'segurança'. "
                    "Omita para listar todos os contratos no intervalo."
                ),
            ),
        },
        required=[],
    ),
)


async def executar_contratos_vencendo(
    *,
    db: AsyncSession,
    dias: int | None = None,
    categoria_objeto: str | None = None,
) -> ResultadoFerramenta:
    """Executor de :data:`CONTRATOS_VENCENDO_DECL`."""
    janela = max(1, min(int(dias or _DIAS_PADRAO), _DIAS_MAX))
    hoje = date.today()
    limite = hoje + timedelta(days=janela)

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

    if categoria_objeto:
        like = f"%{categoria_objeto.strip()}%"
        query = query.where(
            Contrato.objeto.ilike(like) | Contrato.categoria.ilike(like)
        )

    contratos = (await db.execute(query)).scalars().all()

    if not contratos:
        sufixo = f" para o filtro {categoria_objeto!r}" if categoria_objeto else ""
        return ResultadoFerramenta(
            texto=(
                f"Nenhum contrato com vigência terminando nos próximos "
                f"{janela} dias{sufixo}."
            ),
            docs=[],
        )

    cabecalho = (
        f"Contratos com vigência terminando até {limite.isoformat()} "
        f"(janela de {janela} dias a partir de {hoje.isoformat()}). "
        f"{len(contratos)} resultado(s)"
        f"{f' filtrando por {categoria_objeto!r}' if categoria_objeto else ''}."
    )

    return _renderizar_resultado_contratos(
        contratos=contratos,
        cabecalho=cabecalho,
        fonte_tool="contratos_vencendo",
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


# ──────────────────────────────────────────
# Helpers de renderização
# ──────────────────────────────────────────


def _renderizar_resultado_contratos(
    *,
    contratos: list[Contrato],
    cabecalho: str,
    fonte_tool: str,
) -> ResultadoFerramenta:
    """Monta o bloco numerado + lista de DocumentoRelevante para citação."""
    linhas = [cabecalho]
    docs: list[DocumentoRelevante] = []

    for i, c in enumerate(contratos, start=1):
        nome_forn = c.fornecedor.nome if c.fornecedor else "fornecedor não identificado"
        cnpj_forn = c.fornecedor.cpf_cnpj if c.fornecedor else "—"
        valor = float(c.valor_atual or c.valor_inicial or 0)
        valor_txt = _fmt_brl(valor) if valor else "valor não informado"
        objeto = (c.objeto or "").strip().replace("\n", " ") or "—"
        objeto_curto = objeto if len(objeto) <= 220 else objeto[:217] + "..."

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
                },
                score=1.0,
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
