"""
Script de ingestão de dados do PNCP.

Uso:
    cd backend
    python -m scripts.ingest_pncp                     # Padrão: último ano até hoje
    python -m scripts.ingest_pncp --desde 2024-01-01   # Desde uma data específica
    python -m scripts.ingest_pncp --ate 2025-12-31     # Até uma data específica
"""

import argparse
import asyncio
from datetime import date

from app.services.ingestao_pncp import ingerir_tudo
from app.services.rag.indexador import FONTES_POR_SCRIPT
from scripts._rag_auto_reindex import reindex_apos_ingestao


def main():
    parser = argparse.ArgumentParser(description="Ingestão de dados do PNCP")
    parser.add_argument(
        "--desde",
        type=date.fromisoformat,
        default=None,
        help="Data inicial (YYYY-MM-DD). Padrão: 1 jan do ano anterior.",
    )
    parser.add_argument(
        "--ate",
        type=date.fromisoformat,
        default=None,
        help="Data final (YYYY-MM-DD). Padrão: hoje.",
    )
    parser.add_argument(
        "--sem-reindex",
        action="store_true",
        help="Não reindexar o RAG após a ingestão (uso em iterações de dev).",
    )
    args = parser.parse_args()

    async def _run() -> None:
        resultado = await ingerir_tudo(
            data_inicial=args.desde, data_final=args.ate
        )
        print("\n=== Resultado da Ingestão ===")
        for categoria, stats in resultado.items():
            print(f"\n{categoria.upper()}:")
            for k, v in stats.items():
                print(f"  {k}: {v}")

        rag_stats = await reindex_apos_ingestao(
            FONTES_POR_SCRIPT["pncp"],
            sem_reindex=args.sem_reindex,
        )
        if rag_stats is not None:
            print("\n=== Reindexação RAG (CONTRATO, RESUMO_PCA) ===")
            for k, v in rag_stats.items():
                print(f"  {k}: {v}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
