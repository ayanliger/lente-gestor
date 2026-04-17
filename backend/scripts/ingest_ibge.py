"""
Script de ingestão de dados contextuais do IBGE.

Uso:
    cd backend
    python -m scripts.ingest_ibge                             # Padrão: Jequié (2918001), 10 anos
    python -m scripts.ingest_ibge --codigo-ibge 2918001
    python -m scripts.ingest_ibge --ultimos-periodos 6
"""

import argparse
import asyncio

from app.services.ingestao_ibge import ingerir_ibge


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de dados do IBGE")
    parser.add_argument(
        "--codigo-ibge",
        type=str,
        default=None,
        help="Código IBGE do município (7 dígitos). Padrão: configurado em settings.",
    )
    parser.add_argument(
        "--ultimos-periodos",
        type=int,
        default=10,
        help="Quantos anos buscar nas séries do SIDRA. Padrão: 10.",
    )
    args = parser.parse_args()

    stats = asyncio.run(
        ingerir_ibge(
            codigo_ibge=args.codigo_ibge,
            ultimos_periodos=args.ultimos_periodos,
        )
    )

    print("\n=== Resultado da Ingestão (IBGE) ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
