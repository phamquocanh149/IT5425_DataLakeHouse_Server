"""USGS automatic medallion-runner CLI.

One job: the command surface for the auto-runner (``pipeline``): parse flags, build the
config, run the plan+execute, and emit the JSON/text report with the original exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from climate_platform.datasets.usgs import pipeline
from climate_platform.medallion.io import write_json_atomic


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=pipeline.__doc__)
    parser.add_argument("--config", default=None, help="Pipeline TOML (start/end/output/...)")
    parser.add_argument("--grid", default=pipeline._default_grid(), help="Reference grid CSV")
    parser.add_argument("--wbd", default=pipeline._default_wbd(), help="HUC8 boundary GeoPackage")
    parser.add_argument(
        "--overwrite", action="store_true", help="Rebuild every stage even when complete"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report eligible work without writing anything"
    )
    parser.add_argument("--json", action="store_true", help="Print only the JSON report to stdout")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this file")
    return parser.parse_args(argv)


def _print_summary(report):
    details = report.details
    print(
        f"USGS medallion: {details['bronze_root']} -> {details['gold_root']} "
        f"({report.generated_at})"
    )
    print(f"ready={report.ready}")
    if not report.ready:
        print(f"not ready: {report.reason}")
    for stage in ("silver", "weekly", "gold"):
        print(
            f"[{stage}] planned={report.planned[stage]} "
            f"built={report.built[stage]} skipped={report.skipped[stage]}"
        )
    for stage, error in report.failures.items():
        print(f"[{stage}] FAILED: {error}", file=sys.stderr)
    if report.dry_run:
        print("dry-run: no Silver/Weekly/Gold written")


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
    values = tomllib.loads(Path(args.config).read_text()) if args.config else {}
    cfg = pipeline.config_from_values(values)

    report = pipeline.plan(cfg, args.grid, args.wbd, args.overwrite)
    report.dry_run = bool(args.dry_run)
    if report.ready and not args.dry_run:

        def log(message):
            print(message, file=sys.stderr if args.json else sys.stdout, flush=True)

        pipeline.execute(cfg, args.grid, args.wbd, report, log)
    return _emit(report, args)


if __name__ == "__main__":
    raise SystemExit(main())
