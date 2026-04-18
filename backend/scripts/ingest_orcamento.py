"""
Script de ingestão de dados orçamentários do SICONFI (RREO).

Uso:
    cd backend
    python -m scripts.ingest_orcamento --exercicio 2024
    python -m scripts.ingest_orcamento --exercicio 2024 --periodos 5 6
"""

import argparse
import asyncio

from app.services.ingestao_orcamento import ingerir_rreo
from app.services.rag.indexador import FONTES_POR_SCRIPT
from scripts._rag_auto_reindex import reindex_apos_ingestao


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de RREO do SICONFI")
    parser.add_argument(
        "--exercicio",
        type=int,
        required=True,
        help="Ano do exercício (ex: 2024).",
    )
    parser.add_argument(
        "--periodos",
        type=int,
        nargs="+",
        default=None,
        help="Bimestres (1-6). Padrão: todos (1 2 3 4 5 6).",
    )
    parser.add_argument(
        "--sem-reindex",
        action="store_true",
        help="Não reindexar o RAG após a ingestão.",
    )
    args = parser.parse_args()

    async def _run() -> None:
        stats = await ingerir_rreo(
            exercicio=args.exercicio, periodos=args.periodos
        )
        print("\n=== Resultado da Ingestão (RREO) ===")
        print(f"exercicio: {args.exercicio}")
        for k, v in stats.items():
            print(f"  {k}: {v}")

        rag_stats = await reindex_apos_ingestao(
            FONTES_POR_SCRIPT["orcamento"],
            sem_reindex=args.sem_reindex,
        )
        if rag_stats is not None:
            print("\n=== Reindexação RAG (RESUMO_FUNCAO) ===")
            for k, v in rag_stats.items():
                print(f"  {k}: {v}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
