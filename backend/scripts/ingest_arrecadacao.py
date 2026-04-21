"""
Script de ingestão de arrecadação tributária (Município Online).

Uso:
    cd backend
    python -m scripts.ingest_arrecadacao --exercicio 2025
    python -m scripts.ingest_arrecadacao --exercicio 2025 --meses 1 2 3
    python -m scripts.ingest_arrecadacao --exercicio 2024 --com-detalhes
    python -m scripts.ingest_arrecadacao --exercicios 2020 2021 2022 2023 2024 2026

O drill-down por banco (`--com-detalhes`) está desabilitado por padrão
por gerar centenas de requests extras por mês. Reabilite apenas quando
a visualização por banco for necessária.
"""

import argparse
import asyncio

from app.services.ingestao_arrecadacao import ingerir_arrecadacao


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestão de arrecadação tributária do Município Online"
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--exercicio",
        type=int,
        help="Ano do exercício (ex: 2025).",
    )
    grupo.add_argument(
        "--exercicios",
        type=int,
        nargs="+",
        help=(
            "Lista de exercícios para backfill histórico em sequência "
            "(ex: --exercicios 2020 2021 2022)."
        ),
    )
    parser.add_argument(
        "--meses",
        type=int,
        nargs="+",
        default=None,
        help="Meses (1-12). Padrão: todos. Aplicado a cada exercício.",
    )
    parser.add_argument(
        "--com-detalhes",
        action="store_true",
        help=(
            "Executa drill-down por recolhimento (banco recebedor + data). "
            "Desabilitado por padrão porque gera centenas de requests "
            "adicionais por mês."
        ),
    )
    args = parser.parse_args()

    exercicios: list[int] = (
        [args.exercicio] if args.exercicio is not None else list(args.exercicios)
    )

    async def _run() -> None:
        resumo_total: dict[str, int] = {}
        for exercicio in exercicios:
            print(f"\n>>> Ingerindo exercício {exercicio}...")
            stats = await ingerir_arrecadacao(
                exercicio=exercicio,
                meses=args.meses,
                com_detalhes=args.com_detalhes,
            )
            print(f"=== Resultado ({exercicio}) ===")
            for k, v in stats.items():
                print(f"  {k}: {v}")
                if isinstance(v, int):
                    resumo_total[k] = resumo_total.get(k, 0) + v

        if len(exercicios) > 1:
            print("\n=== Consolidado — todos os exercícios ===")
            for k, v in resumo_total.items():
                print(f"  {k}: {v}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
