"""NLDAS per-layer CLIs (build Silver / build Gold from an existing layer).

One job: the manual command surface for the NLDAS Silver and Gold stages, separate from the
automatic runner (``runner_cli``). Each command loops the selected products and reports
failures without aborting the others.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from climate_platform.common.console import configure_stdio
from climate_platform.datasets.nldas import bronze, gold, paths, silver
from climate_platform.medallion.runner import medallion_lock


def silver_main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Build NLDAS Silver from Bronze NetCDF.")
    parser.add_argument("--product", choices=("fora", "noah", "both"), default="both")
    parser.add_argument("--bronze-root", type=Path, default=paths.default_bronze_root())
    parser.add_argument("--references", type=Path, default=paths.default_references())
    parser.add_argument(
        "--output",
        type=Path,
        default=paths.default_silver_root(),
        help="Silver root; each product is written under <output>/<PRODUCT>",
    )
    parser.add_argument("--start", type=date.fromisoformat, help="First Tuesday label, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="Last Tuesday label, YYYY-MM-DD")
    args = parser.parse_args(argv)

    failed = 0
    # The same exclusive lock the automatic runner holds: a manual run cannot clobber a
    # scheduled one (and vice versa) on the shared Silver partitions.
    try:
        with medallion_lock(
            paths.default_lock_file(), "NLDAS medallion already running (lock held)"
        ):
            for product in bronze.resolve_products(args.product):
                try:
                    result = silver.build_silver(
                        product,
                        bronze_root=args.bronze_root,
                        references_dir=args.references,
                        silver_output=args.output / product,
                        start=args.start,
                        end=args.end,
                    )
                except Exception as exc:
                    failed += 1
                    print(
                        f"[{product}] silver failed: {type(exc).__name__}: {exc}", file=sys.stderr
                    )
                    continue
                print(
                    f"[{product}] silver: {len(result['weeks'])} week(s), "
                    f"{result['rows']} row(s) -> {result['output']}"
                )
    except RuntimeError as exc:
        print(f"NLDAS silver: {exc}", file=sys.stderr)
        return 1
    return 1 if failed else 0


def gold_main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Build NLDAS Gold from Silver Parquet.")
    parser.add_argument("--product", choices=("fora", "noah", "both"), default="both")
    parser.add_argument("--silver", type=Path, default=paths.default_silver_root())
    parser.add_argument("--references", type=Path, default=paths.default_references())
    parser.add_argument(
        "--output",
        type=Path,
        default=paths.default_gold_root(),
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
    # Shared with the automatic runner; a manual Gold run cannot race a scheduled one.
    try:
        with medallion_lock(
            paths.default_lock_file(), "NLDAS medallion already running (lock held)"
        ):
            for product in bronze.resolve_products(args.product):
                try:
                    result = gold.build_gold(
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
    except RuntimeError as exc:
        print(f"NLDAS gold: {exc}", file=sys.stderr)
        return 1
    return 1 if failed else 0
