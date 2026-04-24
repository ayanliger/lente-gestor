"""
Script de ingestão de arrecadação anual via SICONFI DCA.

Uso:
    cd backend
    python -m scripts.ingest_arrecadacao_dca --exercicio 2020
    python -m scripts.ingest_arrecadacao_dca --exercicios 2020 2021 2022

Usado primariamente como backfill histórico para 2020–2022, período em que o
portal Município Online não republicou dados realizados. Para 2023+, a fonte
preferida continua sendo `make ingest-arrecadacao-historico`.
"""

import argparse
import asyncio

from app.services.ingestao_arrecadacao_historica import ingerir_arrecadacao_dca


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestão de arrecadação anual via SICONFI DCA (Anexo I-C)."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--exercicio",
        type=int,
        help="Ano do exercício (ex: 2020).",
    )
    grupo.add_argument(
        "--exercicios",
        type=int,
        nargs="+",
        help="Lista de exercícios para backfill (ex: --exercicios 2020 2021 2022).",
    )
    parser.add_argument(
        "--no-anexo",
        default="DCA-Anexo I-C",
        help="Anexo DCA a consultar. Padrão: Balanço Orçamentário (I-C).",
    )
    args = parser.parse_args()

    exercicios = (
        [args.exercicio] if args.exercicio is not None else list(args.exercicios)
    )

    async def _run() -> None:
        stats = await ingerir_arrecadacao_dca(
            exercicios=exercicios, no_anexo=args.no_anexo
        )
        print("\n=== Resultado (SICONFI DCA) ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
