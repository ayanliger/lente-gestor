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
    args = parser.parse_args()

    resultado = asyncio.run(ingerir_tudo(data_inicial=args.desde, data_final=args.ate))

    print("\n=== Resultado da Ingestão ===")
    for categoria, stats in resultado.items():
        print(f"\n{categoria.upper()}:")
        for k, v in stats.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
