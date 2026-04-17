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
    args = parser.parse_args()

    stats = asyncio.run(
        ingerir_rreo(exercicio=args.exercicio, periodos=args.periodos)
    )

    print("\n=== Resultado da Ingestão (RREO) ===")
    print(f"exercicio: {args.exercicio}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
