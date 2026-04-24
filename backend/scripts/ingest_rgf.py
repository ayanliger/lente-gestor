"""
Script de ingestão do RGF do SICONFI + derivação dos indicadores fiscais.

Uso:
    cd backend
    python -m scripts.ingest_rgf --exercicio 2024
    python -m scripts.ingest_rgf --exercicio 2024 --quadrimestres 1 2
    python -m scripts.ingest_rgf --exercicio 2024 --co-poder L
    python -m scripts.ingest_rgf --exercicio 2024 --no-derivar
    python -m scripts.ingest_rgf --exercicios 2020 2021 2022 2023 2024 2025
"""

import argparse
import asyncio

from app.services.indicadores_fiscais import derivar_indicadores_fiscais
from app.services.ingestao_orcamento import ingerir_rgf
from app.services.rag.indexador import FONTES_POR_SCRIPT
from scripts._rag_auto_reindex import reindex_apos_ingestao


async def _executar_ano(
    exercicio: int, args: argparse.Namespace
) -> tuple[dict, dict | None]:
    stats_rgf = await ingerir_rgf(
        exercicio=exercicio,
        quadrimestres=args.quadrimestres,
        co_poder=args.co_poder,
    )

    stats_indicadores: dict | None = None
    if not args.no_derivar:
        stats_indicadores = await derivar_indicadores_fiscais(
            exercicio=exercicio
        )

    return stats_rgf, stats_indicadores


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestão de RGF do SICONFI + derivação de indicadores fiscais"
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--exercicio", type=int, help="Ano (ex: 2024).")
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
        "--quadrimestres",
        type=int,
        nargs="+",
        default=None,
        help="Quadrimestres (1-3). Padrão: todos (1 2 3).",
    )
    parser.add_argument(
        "--co-poder",
        type=str,
        default="E",
        choices=["E", "L"],
        help="Poder (E=Executivo, L=Legislativo). Padrão: E.",
    )
    parser.add_argument(
        "--no-derivar",
        action="store_true",
        help="Não derivar indicadores fiscais após a ingestão.",
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
        derivou_algum = False
        for exercicio in exercicios:
            print(f"\n>>> Ingerindo exercício {exercicio}...")
            stats_rgf, stats_indicadores = await _executar_ano(exercicio, args)

            print(f"=== Resultado (RGF {exercicio}, poder={args.co_poder}) ===")
            for k, v in stats_rgf.items():
                print(f"  {k}: {v}")

            if stats_indicadores is not None:
                derivou_algum = True
                print(f"=== Indicadores Fiscais Derivados ({exercicio}) ===")
                for k, v in stats_indicadores.items():
                    print(f"  {k}: {v}")

        # Reindex só faz sentido se algum exercício derivou indicadores.
        if derivou_algum:
            rag_stats = await reindex_apos_ingestao(
                FONTES_POR_SCRIPT["rgf"],
                sem_reindex=args.sem_reindex,
            )
            if rag_stats is not None:
                print("\n=== Reindexação RAG (INDICADOR_FISCAL) ===")
                for k, v in rag_stats.items():
                    print(f"  {k}: {v}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
