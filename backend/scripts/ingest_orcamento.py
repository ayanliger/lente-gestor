"""
Script de ingestão de dados orçamentários do SICONFI (RREO).

Uso:
    cd backend
    python -m scripts.ingest_orcamento --exercicio 2024
    python -m scripts.ingest_orcamento --exercicio 2024 --periodos 5 6
    python -m scripts.ingest_orcamento --exercicios 2020 2021 2022 2023 2024 2025 2026
"""

import argparse
import asyncio

from app.services.ingestao_orcamento import ingerir_rreo
from app.services.rag.indexador import FONTES_POR_SCRIPT
from scripts._rag_auto_reindex import reindex_apos_ingestao


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de RREO do SICONFI")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--exercicio",
        type=int,
        help="Ano do exercício (ex: 2024).",
    )
    grupo.add_argument(
        "--exercicios",
        type=int,
        nargs="+",
        help=(
            "Lista de exercícios para backfill histórico em sequência "
            "(ex: --exercicios 2020 2021 2022). Reindex RAG roda uma "
            "única vez ao final."
        ),
    )
    parser.add_argument(
        "--periodos",
        type=int,
        nargs="+",
        default=None,
        help="Bimestres (1-6). Padrão: todos (1 2 3 4 5 6). Aplicado a cada exercício.",
    )
    parser.add_argument(
        "--sem-reindex",
        action="store_true",
        help="Não reindexar o RAG após a ingestão.",
    )
    args = parser.parse_args()

    exercicios: list[int] = (
        [args.exercicio] if args.exercicio is not None else list(args.exercicios)
    )

    async def _run() -> None:
        resumo_total: dict[str, int] = {}
        for exercicio in exercicios:
            print(f"\n>>> Ingerindo exercício {exercicio}...")
            stats = await ingerir_rreo(
                exercicio=exercicio, periodos=args.periodos
            )
            print(f"=== Resultado (RREO {exercicio}) ===")
            for k, v in stats.items():
                print(f"  {k}: {v}")
                if isinstance(v, int):
                    resumo_total[k] = resumo_total.get(k, 0) + v

        if len(exercicios) > 1:
            print("\n=== Consolidado — todos os exercícios ===")
            for k, v in resumo_total.items():
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
