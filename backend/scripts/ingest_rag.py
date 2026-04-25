"""
Script de reindexação manual da base RAG.

Uso:
    cd backend
    python -m scripts.ingest_rag                          # tudo
    python -m scripts.ingest_rag --fontes contrato indicador_fiscal
    python -m scripts.ingest_rag --dry-run                # sem embedar nem gravar
    python -m scripts.ingest_rag --lote 32                # batch menor

Auto-reindex nos scripts `ingest_pncp`, `ingest_orcamento` e `ingest_rgf` é
o caminho padrão; este script é o recurso para rebuild completo, smoke
tests ou iteração manual.
"""

from __future__ import annotations

import argparse
import asyncio

from app.models.rag import FonteDocumento
from app.services.rag.indexador import reindexar

_FONTE_POR_STRING = {f.value.lower(): f for f in FonteDocumento}
_FONTE_POR_STRING.update({f.value: f for f in FonteDocumento})
# Aliases curtos para UX de CLI
_ALIASES = {
    "contrato": FonteDocumento.CONTRATO,
    "indicador_fiscal": FonteDocumento.INDICADOR_FISCAL,
    "indicador": FonteDocumento.INDICADOR_FISCAL,
    "resumo_funcao": FonteDocumento.RESUMO_FUNCAO,
    "funcao": FonteDocumento.RESUMO_FUNCAO,
    "resumo_pca": FonteDocumento.RESUMO_PCA,
    "pca": FonteDocumento.RESUMO_PCA,
    "resumo_receita": FonteDocumento.RESUMO_RECEITA,
    "receita": FonteDocumento.RESUMO_RECEITA,
    "resumo_natureza_despesa": FonteDocumento.RESUMO_NATUREZA_DESPESA,
    "natureza": FonteDocumento.RESUMO_NATUREZA_DESPESA,
    "natureza_despesa": FonteDocumento.RESUMO_NATUREZA_DESPESA,
}


def _parse_fontes(valores: list[str] | None) -> list[FonteDocumento] | None:
    if not valores:
        return None
    fontes: list[FonteDocumento] = []
    for v in valores:
        chave = v.lower()
        fonte = _ALIASES.get(chave) or _FONTE_POR_STRING.get(chave)
        if fonte is None:
            opcoes = ", ".join(sorted(_ALIASES.keys()))
            raise SystemExit(f"fonte desconhecida: {v!r} — use uma de: {opcoes}")
        if fonte not in fontes:
            fontes.append(fonte)
    return fontes


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindexação RAG.")
    parser.add_argument(
        "--fontes",
        nargs="+",
        default=None,
        help=(
            "Subconjunto a reindexar. Opções: contrato, indicador_fiscal, "
            "resumo_funcao, resumo_pca, resumo_receita, "
            "resumo_natureza_despesa. Padrão: todas."
        ),
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=64,
        help="Tamanho do batch de embedding (padrão: 64).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Renderiza e loga contagens, mas não embeda nem escreve.",
    )
    args = parser.parse_args()

    fontes = _parse_fontes(args.fontes)
    stats = asyncio.run(
        reindexar(fontes=fontes, lote=args.lote, dry_run=args.dry_run)
    )

    rotulo = "(dry-run) " if args.dry_run else ""
    print(f"\n=== Reindexação RAG {rotulo}===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
