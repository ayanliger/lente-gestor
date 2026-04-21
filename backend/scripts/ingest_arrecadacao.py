"""
Script de ingestão de arrecadação tributária (Município Online).

Uso:
    cd backend
    python -m scripts.ingest_arrecadacao --exercicio 2025
    python -m scripts.ingest_arrecadacao --exercicio 2025 --meses 1 2 3
    python -m scripts.ingest_arrecadacao --exercicio 2024 --com-detalhes

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
    parser.add_argument(
        "--exercicio",
        type=int,
        required=True,
        help="Ano do exercício (ex: 2025).",
    )
    parser.add_argument(
        "--meses",
        type=int,
        nargs="+",
        default=None,
        help="Meses (1-12). Padrão: todos.",
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

    async def _run() -> None:
        stats = await ingerir_arrecadacao(
            exercicio=args.exercicio,
            meses=args.meses,
            com_detalhes=args.com_detalhes,
        )
        print("\n=== Resultado da Ingestão (Arrecadação) ===")
        print(f"exercicio: {args.exercicio}")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
