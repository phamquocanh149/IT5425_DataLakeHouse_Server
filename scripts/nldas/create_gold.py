"""Build NLDAS Gold from Silver Parquet for one or both products."""

import argparse
import sys
from datetime import date
from pathlib import Path

import gold_common
import nldas_common


def main(argv=None):
    nldas_common.configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=("fora", "noah", "both"), default="both")
    parser.add_argument(
        "--silver",
        type=Path,
        default=nldas_common.default_silver_root(),
        help="Silver root produced by create_silver.py",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=nldas_common.default_references(),
        help="Reference grid directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=nldas_common.default_gold_root(),
        help="Gold root; each product is written under <output>/<PRODUCT>",
    )
    parser.add_argument("--start", type=date.fromisoformat, help="First week label, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="Last week label, YYYY-MM-DD")
    parser.add_argument(
        "--keep-r25",
        action="store_true",
        help="Keep R25 instead of dropping it (must match the output directory policy)",
    )
    args = parser.parse_args(argv)

    failed = 0
    for product in nldas_common.resolve_products(args.product):
        try:
            result = gold_common.build_gold(
                product,
                silver_input=args.silver / product,
                references_dir=args.references,
                gold_output=args.output / product,
                start=args.start,
                end=args.end,
                keep_r25=args.keep_r25,
            )
        except Exception as exc:
            failed += 1
            print(f"[{product}] gold failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        print(
            f"[{product}] gold: {len(result['weeks'])} week(s), "
            f"{result['rows']} row(s) -> {result['output']}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
