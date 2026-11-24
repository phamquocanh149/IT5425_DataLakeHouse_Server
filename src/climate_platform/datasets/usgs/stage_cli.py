"""USGS medallion stage CLI (silver / weekly / gold / validate-gold / build-gold).

One job: the manual, per-stage command surface for the USGS medallion, kept separate from
the automatic runner (``pipeline``) and the crawl CLI (``cli``).
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from climate_platform.datasets.usgs.config import Config
from climate_platform.datasets.usgs.gate import conditions_met
from climate_platform.datasets.usgs.gold import gold
from climate_platform.datasets.usgs.gold_validate import validate_gold
from climate_platform.datasets.usgs.method import METHOD
from climate_platform.datasets.usgs.paths import default_bronze_root
from climate_platform.datasets.usgs.silver import silver
from climate_platform.datasets.usgs.weekly import weekly
from climate_platform.medallion.runner import medallion_lock


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["silver", "weekly", "gold", "validate-gold", "build-gold"]
    )
    parser.add_argument("--config", default=None)
    parser.add_argument(
        "--grid", default=str(default_bronze_root() / "grid_huc_inputs" / "grid.csv")
    )
    parser.add_argument(
        "--wbd", default=str(default_bronze_root() / "grid_huc_inputs" / "wbd" / "WBDHU8.gpkg")
    )
    parser.add_argument("--silver-run", type=Path)
    parser.add_argument("--weekly-run", type=Path)
    parser.add_argument("--gold-run", type=Path)
    args = parser.parse_args(argv)
    values = tomllib.loads(Path(args.config).read_text()) if args.config else {}
    cfg = Config(**values).check()
    if (cfg.start, cfg.end) != (METHOD["baseline_start"], METHOD["baseline_end"]):
        parser.error("This method requires exact 2020\u20132022 scope")
    root = Path(cfg.output)
    root.mkdir(parents=True, exist_ok=True)
    lock_message = f"USGS pipeline already running (lock: {root / '.pipeline.lock'})"
    with medallion_lock(root / ".pipeline.lock", lock_message):
        if args.command in ("silver", "build-gold"):
            readiness = conditions_met(cfg)
            if not readiness.ready:
                print(f"USGS medallion not ready: {readiness.reason}")
                return 2
            args.silver_run = silver(cfg, Path(args.grid), Path(args.wbd))
            print(args.silver_run)
        if args.command in ("weekly", "build-gold"):
            if not args.silver_run:
                parser.error("--silver-run required")
            args.weekly_run = weekly(args.silver_run)
            print(args.weekly_run)
        if args.command in ("gold", "build-gold"):
            if not args.weekly_run:
                parser.error("--weekly-run required")
            print(gold(args.weekly_run))
        if args.command == "validate-gold":
            if not args.gold_run:
                parser.error("--gold-run required")
            report = validate_gold(args.gold_run)
            print(json.dumps(report, indent=2))
            return 0 if report["passed"] else 2
    return 0
