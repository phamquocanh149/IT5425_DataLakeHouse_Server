"""Build NLDAS Silver from Bronze NetCDF for one or both products."""

import argparse
import sys
from datetime import date
from pathlib import Path

import nldas_common
import silver_common


def main(argv=None):
    nldas_common.configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=("fora", "noah", "both"), default="both")
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=nldas_common.default_bronze_root(),
        help="Bronze NetCDF root (default: duy-nldas-script/src/bronze/data)",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=nldas_common.default_references(),
        help="Reference grid and Tuesday calendar directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=nldas_common.default_silver_root(),
        help="Silver root; each product is written under <output>/<PRODUCT>",
    )
    parser.add_argument("--start", type=date.fromisoformat, help="First Tuesday label, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="Last Tuesday label, YYYY-MM-DD")
    args = parser.parse_args(argv)

    failed = 0
    for product in nldas_common.resolve_products(args.product):
        try:
            result = silver_common.build_silver(
                product,
                bronze_root=args.bronze_root,
                references_dir=args.references,
                silver_output=args.output / product,
                start=args.start,
                end=args.end,
            )
        except Exception as exc:
            failed += 1
            print(f"[{product}] silver failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        print(
            f"[{product}] silver: {len(result['weeks'])} week(s), "
            f"{result['rows']} row(s) -> {result['output']}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
