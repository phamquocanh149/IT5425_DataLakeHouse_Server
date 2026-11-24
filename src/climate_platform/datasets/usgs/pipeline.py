"""USGS medallion orchestration: plan then execute Silver -> Weekly -> Gold.

One job: decide which stages to build for the current client-provided Bronze (plan) and run
them in order under the shared lock (execute). Science lives in ``silver``/``weekly``/``gold``;
eligibility lives in ``gate``. ``stop_on_failure`` keeps the fail-closed behaviour.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from climate_platform.datasets.usgs.config import Config
from climate_platform.datasets.usgs.gate import conditions_met
from climate_platform.datasets.usgs.gold import gold
from climate_platform.datasets.usgs.method import METHOD
from climate_platform.datasets.usgs.paths import default_silver_root, default_gold_root
from climate_platform.datasets.usgs.silver import silver
from climate_platform.datasets.usgs.weekly import weekly
from climate_platform.medallion.contracts import RunReport
from climate_platform.medallion.runner import MedallionRunner

SILVER_ROOT = default_silver_root()
GOLD_ROOT = default_gold_root()
ORDER = ("silver", "weekly", "gold")


def _completed_runs(root, stage_name):
    """Newest-last list of (completed_at, run_dir, manifest) for a completed medallion stage."""
    base = Path(root) / "medallion" / stage_name
    if not base.exists():
        return []
    runs = []
    for manifest in base.glob("*/manifest.json"):
        try:
            data = json.loads(manifest.read_text())
        except (OSError, ValueError):
            continue
        if data.get("status") == "complete":
            runs.append((data.get("completed_at", ""), manifest.parent, data))
    return sorted(runs, key=lambda item: item[0])


def _latest(root, stage_name, **match):
    for _, run, data in reversed(_completed_runs(root, stage_name)):
        if all(data.get(key) == value for key, value in match.items()):
            return run, data
    return None, None


def plan(cfg, grid, wbd, overwrite=False) -> RunReport:
    """Inspect Bronze/medallion state and decide which stages a real run would build.

    Eligibility re-runs crawl validation and the raw audit, refreshing their report
    artifacts; no Silver/Weekly/Gold output is written during planning.
    """
    readiness = conditions_met(cfg)
    silver_run, _ = _latest(SILVER_ROOT, "silver") if readiness.ready else (None, None)
    weekly_run = gold_run = None
    if silver_run is not None:
        weekly_run, _ = _latest(SILVER_ROOT, "weekly", silver_run=str(silver_run.resolve()))
    if weekly_run is not None:
        gold_run, _ = _latest(GOLD_ROOT, "gold", weekly_run=str(weekly_run.resolve()))

    plan_silver = bool(readiness.ready and (overwrite or silver_run is None))
    plan_weekly = bool(readiness.ready and (plan_silver or weekly_run is None))
    plan_gold = bool(readiness.ready and (plan_weekly or gold_run is None))

    return RunReport(
        source="usgs",
        ready=readiness.ready,
        reason=readiness.reason,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        planned={"silver": plan_silver, "weekly": plan_weekly, "gold": plan_gold},
        built={"silver": False, "weekly": False, "gold": False},
        skipped={
            "silver": not plan_silver,
            "weekly": not plan_weekly,
            "gold": not plan_gold,
        },
        details={
            "bronze_root": str(Path(cfg.output).resolve()),
            "silver_root": str(Path(SILVER_ROOT).resolve()),
            "gold_root": str(Path(GOLD_ROOT).resolve()),
            "grid": str(grid),
            "wbd": str(wbd),
            "silver_run": str(silver_run) if silver_run is not None else None,
            "weekly_run": str(weekly_run) if weekly_run is not None else None,
            "gold_run": str(gold_run) if gold_run is not None else None,
        },
    )


def execute(cfg, grid, wbd, report: RunReport, log=print) -> RunReport:
    """Build planned stages under the shared runner lock; stop at the first failure."""
    lock_path = Path(cfg.output) / ".pipeline.lock"
    state = {
        "silver": Path(report.details["silver_run"]) if report.details.get("silver_run") else None,
        "weekly": Path(report.details["weekly_run"]) if report.details.get("weekly_run") else None,
        "gold": Path(report.details["gold_run"]) if report.details.get("gold_run") else None,
    }

    def run_silver():
        state["silver"] = silver(cfg, Path(grid), Path(wbd))
        return state["silver"]

    def run_weekly():
        if state["silver"] is None:
            raise RuntimeError("silver run unavailable")
        state["weekly"] = weekly(state["silver"])
        return state["weekly"]

    def run_gold():
        if state["weekly"] is None:
            raise RuntimeError("weekly run unavailable")
        state["gold"] = gold(state["weekly"])
        return state["gold"]

    runner = MedallionRunner(
        lock_path=lock_path,
        order=ORDER,
        log=log,
        lock_message=f"USGS pipeline already running (lock: {lock_path})",
        stop_on_failure=True,
    )
    runner.run(report, {"silver": run_silver, "weekly": run_weekly, "gold": run_gold})
    for name, path in state.items():
        if path is not None:
            report.details[f"{name}_run"] = str(path)
    return report


def run(cfg, grid, wbd, overwrite=False, dry_run=False, log=print) -> RunReport:
    report = plan(cfg, grid, wbd, overwrite)
    report.dry_run = bool(dry_run)
    if report.ready and not dry_run:
        execute(cfg, grid, wbd, report, log)
    return report


def _default_grid():
    from climate_platform.datasets.usgs.paths import default_bronze_root

    return str(default_bronze_root() / "grid_huc_inputs" / "grid.csv")


def _default_wbd():
    from climate_platform.datasets.usgs.paths import default_bronze_root

    return str(default_bronze_root() / "grid_huc_inputs" / "wbd" / "WBDHU8.gpkg")


def config_from_values(values) -> Config:
    """Build a checked Config from TOML/CLI values, requiring the fixed 2020-2022 scope."""
    cfg = Config(**values).check()
    if (cfg.start, cfg.end) != (METHOD["baseline_start"], METHOD["baseline_end"]):
        raise ValueError("This method requires exact 2020-2022 scope")
    Path(cfg.output).mkdir(parents=True, exist_ok=True)
    return cfg
