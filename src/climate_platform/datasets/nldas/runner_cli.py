"""NLDAS automatic medallion-runner CLI.

One job: the command surface for the NLDAS auto-runner: parse flags, plan+execute via
``datasets.nldas.pipeline``, then emit the JSON/text report with the original exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from climate_platform.common.console import configure_stdio
from climate_platform.datasets.nldas import bronze, paths, pipeline
from climate_platform.medallion.io import write_json_atomic


def parse_args(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description=pipeline.__doc__)
    parser.add_argument("--product", choices=("fora", "noah", "both"), default="both")
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=paths.default_bronze_root(),
        help="Bronze NetCDF root (default: duy-nldas-script/src/bronze/data)",
    )
    parser.add_argument(
        "--references",
        type=Path,
        default=paths.default_references(),
        help="Reference grid and Tuesday calendar directory",
    )
    parser.add_argument(
        "--silver-root",
        type=Path,
        default=paths.default_silver_root(),
        help="Silver root; each product lives under <root>/<PRODUCT>",
    )
    parser.add_argument(
        "--gold-root",
        type=Path,
        default=paths.default_gold_root(),
        help="Gold root; each product lives under <root>/<PRODUCT>",
    )
    parser.add_argument("--start", type=date.fromisoformat, help="First Tuesday label, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, help="Last Tuesday label, YYYY-MM-DD")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report eligible work without writing anything"
    )
    parser.add_argument("--json", action="store_true", help="Print only the JSON report to stdout")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this file")
    parser.add_argument(
        "--keep-r25",
        action="store_true",
        help="Keep R25 in Gold (must match the output directory policy)",
    )
    parser.add_argument("--lock-file", type=Path, default=paths.default_lock_file())
    return parser.parse_args(argv)


def _print_summary(report):
    details = report.details
    print(
        f"NLDAS medallion: {details['bronze_root']} -> {details['gold_root']} "
        f"({report.generated_at})"
    )
    for product, data in details["products"].items():
        print(
            f"[{product}] bronze_hours={data['bronze_hours']} "
            f"ready={len(data['ready_weeks'])} "
            f"silver_planned={len(data['planned_silver'])} "
            f"gold_planned={len(data['planned_gold'])} "
            f"silver_built={len(data['built_silver'])} "
            f"gold_built={len(data['built_gold'])}"
        )
    for product, error in report.failures.items():
        print(f"[{product}] FAILED: {error}", file=sys.stderr)
    if report.dry_run:
        print("dry-run: nothing written")


def _emit(report, args):
    if args.report:
        write_json_atomic(args.report, report.as_dict())
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        _print_summary(report)
    return report.exit_code()


def main(argv=None):
    args = parse_args(argv)
    context = pipeline.NldasContext(
        products=bronze.resolve_products(args.product),
        bronze_root=args.bronze_root,
        references=args.references,
        silver_root=args.silver_root,
        gold_root=args.gold_root,
        start=args.start,
        end=args.end,
        keep_r25=args.keep_r25,
        lock_file=args.lock_file,
        dry_run=args.dry_run,
    )

    def log(message):
        print(message, file=sys.stderr if args.json else sys.stdout, flush=True)

    try:
        report = pipeline.run(context, log)
    except RuntimeError as exc:
        print(f"NLDAS medallion: {exc}", file=sys.stderr)
        return 1

    report.dry_run = bool(args.dry_run)
    return _emit(report, args)


if __name__ == "__main__":
    raise SystemExit(main())
