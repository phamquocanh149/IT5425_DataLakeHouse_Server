"""NOAA automatic medallion-runner CLI.

One job: the command surface for the NOAA auto-runner: parse flags, plan+execute via
``datasets.noaa.pipeline``, then emit the JSON/text report with the original exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from climate_platform.common.console import configure_stdio
from climate_platform.datasets.noaa import paths, pipeline
from climate_platform.medallion.io import write_json_atomic


def parse_args(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description=pipeline.__doc__)
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=paths.bronze_root(),
        help="Bronze root holding ingest_date=* snapshots (default: data_lake/bronze/noaa)",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=None,
        help="Explicit Bronze snapshot directory (overrides latest-snapshot discovery)",
    )
    parser.add_argument("--silver-root", type=Path, default=paths.silver_root())
    parser.add_argument("--gold-root", type=Path, default=paths.gold_root())
    parser.add_argument("--week-dates-csv", type=Path, default=paths.default_week_dates_csv())
    parser.add_argument(
        "--usdm-csv",
        type=Path,
        default=None,
        help="USDM Gold usdmfinal.csv; when present it refreshes the Tuesday calendar",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report eligible work without writing anything"
    )
    parser.add_argument("--json", action="store_true", help="Print only the JSON report to stdout")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this file")
    parser.add_argument(
        "--overwrite", action="store_true", help="Rebuild Silver/Gold even when outputs exist"
    )
    parser.add_argument("--lock-file", type=Path, default=paths.default_lock_file())
    return parser.parse_args(argv)


def _print_summary(report):
    details = report.details
    print(
        f"NOAA medallion: {details['bronze_root']} -> {details['gold_root']} "
        f"({report.generated_at})"
    )
    print(f"snapshot={details['snapshot']} ready={report.ready} calendar={details['calendar']}")
    if not report.ready:
        print(f"not ready: {report.reason}")
    for stage in ("silver", "gold"):
        print(
            f"[{stage}] planned={report.planned[stage]} "
            f"built={report.built[stage]} skipped={report.skipped[stage]}"
        )
    for stage, error in report.failures.items():
        print(f"[{stage}] FAILED: {error}", file=sys.stderr)
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
    context = pipeline.NoaaContext(
        bronze_root=args.bronze_root,
        silver_root=args.silver_root,
        gold_root=args.gold_root,
        week_dates_csv=args.week_dates_csv,
        usdm_csv=args.usdm_csv,
        snapshot_dir=args.snapshot_dir,
        lock_file=args.lock_file,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    def log(message):
        print(message, file=sys.stderr if args.json else sys.stdout, flush=True)

    try:
        report = pipeline.run(context, log)
    except RuntimeError as exc:
        print(f"NOAA medallion: {exc}", file=sys.stderr)
        return 1

    report.dry_run = bool(args.dry_run)
    return _emit(report, args)


if __name__ == "__main__":
    raise SystemExit(main())
