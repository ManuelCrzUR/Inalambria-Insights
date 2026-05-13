#!/usr/bin/env python3
"""
TEMP_score_phones.py - CLI para scoring de teléfonos

Uso:
    python scripts/TEMP_score_phones.py 573001234567
    python scripts/TEMP_score_phones.py 573001234567 573009876543 --lookback-days 365
    python scripts/TEMP_score_phones.py --file phones.txt --output resultado.json --ref loan_app_123
"""

import sys
import json
import argparse
from pathlib import Path

# Agregar parent dir al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from s3_query.TEMP_phone_scorer import score_phones


def main():
    parser = argparse.ArgumentParser(
        description="Score teléfonos por SMS (últimos 365 días)"
    )

    parser.add_argument(
        "phones",
        nargs="*",
        help="Uno o más números de teléfono (ej: 573001234567)",
    )

    parser.add_argument(
        "--file",
        type=Path,
        help="Leer teléfonos desde archivo (uno por línea)",
    )

    parser.add_argument(
        "--lookback-days",
        type=int,
        default=365,
        help="Días hacia atrás (default 365)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Guardar JSON a archivo (default: stdout)",
    )

    parser.add_argument(
        "--ref",
        "--request-reference",
        dest="request_reference",
        help="ID de referencia (loan_app_123, etc.)",
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent.parent / "config" / "all_rule_classifications.csv",
        help="Path a CSV de clasificaciones",
    )

    parser.add_argument(
        "--s3-bucket",
        default="s3://inalambria-db-sms/imp3",
        help="S3 bucket path",
    )

    parser.add_argument(
        "--s3-region",
        default="us-east-2",
        help="AWS region (default us-east-2)",
    )

    args = parser.parse_args()

    # Recopilar teléfonos
    phone_list = args.phones.copy() if args.phones else []

    if args.file:
        if not args.file.exists():
            print(f"Error: archivo no encontrado: {args.file}", file=sys.stderr)
            sys.exit(1)

        with open(args.file) as f:
            phone_list.extend([line.strip() for line in f if line.strip()])

    if not phone_list:
        parser.print_help()
        print("\nError: debe proporcionar teléfonos", file=sys.stderr)
        sys.exit(1)

    # Score
    try:
        results = score_phones(
            phones=phone_list,
            lookback_days=args.lookback_days,
            classifications_csv=args.csv,
            s3_bucket=args.s3_bucket,
            s3_region=args.s3_region,
            request_reference=args.request_reference,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error durante scoring: {e}", file=sys.stderr)
        sys.exit(1)

    # Formato de salida
    output_json = json.dumps(results, indent=2, default=str)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"✓ Guardado a {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
