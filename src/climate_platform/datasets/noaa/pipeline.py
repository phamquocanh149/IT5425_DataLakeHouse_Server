"""NOAA medallion orchestration: plan then execute Silver -> Gold.

One job: given a resolved context, decide which stages to build (plan) and run them under
the shared lock (execute). The science lives in ``silver``/``gold``; this module only wires
the gate, the plan and the runner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from climate_platform.datasets.noaa import bronze, paths, spec
from climate_platform.medallion.contracts import RunReport
from climate_platform.medallion.io import outputs_complete
from climate_platform.medallion.runner import medallion_lock

logger = logging.getLogger("climate_platform.noaa")


@dataclass
class NoaaContext:
    bronze_root: Path
    silver_root: Path
    gold_root: Path
    week_dates_csv: Path
    usdm_csv: Optional[Path] = None
    snapshot_dir: Optional[Path] = None
    lock_file: Path = field(default_factory=paths.default_lock_file)
    overwrite: bool = False
    dry_run: bool = False


def default_context(**overrides) -> NoaaContext:
    """Context with every path defaulted, so callers pass only what they override."""
    values = {
        "bronze_root": paths.bronze_root(),
        "silver_root": paths.silver_root(),
        "gold_root": paths.gold_root(),
        "week_dates_csv": paths.default_week_dates_csv(),
    }
    values.update({key: value for key, value in overrides.items() if value is not None})
    return NoaaContext(**values)


def _complete(root, marker, names) -> bool:
    """A layer is done only when its completion marker records every output at its size."""
    return outputs_complete(root, marker, names)


def _calendar(ctx: NoaaContext):
    """Return (source_label, usable) for the USDM Tuesday calendar Gold attaches to."""
    if ctx.usdm_csv is not None and Path(ctx.usdm_csv).is_file():
        return f"usdm_usdmfinal ({Path(ctx.usdm_csv).name})", True
    week_dates = Path(ctx.week_dates_csv)
    if week_dates.is_file():
        return week_dates.name, True
    return "none", False


def selected_snapshot(ctx: NoaaContext) -> Path:
    return (
        Path(ctx.snapshot_dir)
        if ctx.snapshot_dir is not None
        else bronze.latest_snapshot(ctx.bronze_root)
    )


def plan(ctx: NoaaContext) -> RunReport:
    """Inspect Bronze/Silver/Gold and decide what a real run would build (no writes)."""
    snapshot = selected_snapshot(ctx)
    readiness = bronze.inspect(snapshot)
    calendar_label, calendar_ok = _calendar(ctx)
    silver_present = _complete(ctx.silver_root, spec.COMPLETE_MARKER, spec.SILVER_OUTPUTS)
    gold_present = _complete(ctx.gold_root, spec.COMPLETE_MARKER, spec.GOLD_OUTPUTS)

    plan_silver = bool(readiness.ready and (ctx.overwrite or not silver_present))
    plan_gold = bool(readiness.ready and calendar_ok and (ctx.overwrite or not gold_present))

    return RunReport(
        source="noaa",
        ready=readiness.ready,
        reason=readiness.reason,
        dry_run=ctx.dry_run,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        planned={"silver": plan_silver, "gold": plan_gold},
        built={"silver": False, "gold": False},
        skipped={"silver": not plan_silver, "gold": not plan_gold},
        details={
            "bronze_root": str(Path(ctx.bronze_root).resolve()),
            "silver_root": str(Path(ctx.silver_root).resolve()),
            "gold_root": str(Path(ctx.gold_root).resolve()),
            "snapshot": str(snapshot),
            "calendar": calendar_label,
            "silver_present": silver_present,
            "gold_present": gold_present,
        },
    )


def execute(ctx: NoaaContext, report: RunReport, log=logger.info) -> RunReport:
    """Build planned Silver then Gold under an exclusive lock; skip already-complete work."""
    lock_message = f"NOAA medallion already running (lock: {ctx.lock_file})"
    with medallion_lock(ctx.lock_file, lock_message):
        silver_failed = False
        if report.planned["silver"]:
            from climate_platform.datasets.noaa.silver import (
                NOAABronzeToSilverPipeline,
                PipelineConfig,
            )

            try:
                pipeline = NOAABronzeToSilverPipeline(
                    PipelineConfig(
                        bronze_root=Path(ctx.bronze_root),
                        silver_root=Path(ctx.silver_root),
                        snapshot_dir=Path(report.details["snapshot"]),
                        overwrite=ctx.overwrite,
                    )
                )
                summary = pipeline.run()
                report.built["silver"] = summary.get("status") in (None, "SUCCESS")
                log(f"[silver] status={summary.get('status', 'SUCCESS')}")
            except Exception as exc:
                report.failures["silver"] = f"{type(exc).__name__}: {exc}"
                silver_failed = True
                log(f"[silver] FAILED: {report.failures['silver']}")

        silver_present = _complete(ctx.silver_root, spec.COMPLETE_MARKER, spec.SILVER_OUTPUTS)
        calendar_label, calendar_ok = _calendar(ctx)
        gold_present = _complete(ctx.gold_root, spec.COMPLETE_MARKER, spec.GOLD_OUTPUTS)
        report.details["silver_present"] = silver_present
        report.details["gold_present"] = gold_present
        report.details["calendar"] = calendar_label
        # Gold must never be built from a Silver layer that is incomplete or that just failed.
        gold_eligible = bool(
            report.ready
            and silver_present
            and not silver_failed
            and calendar_ok
            and (ctx.overwrite or not gold_present)
        )
        report.planned["gold"] = gold_eligible
        report.skipped["gold"] = not gold_eligible
        if gold_eligible:
            from climate_platform.datasets.noaa import gold

            try:
                gold_report = gold.build_outputs(
                    ctx.silver_root,
                    ctx.gold_root,
                    ctx.week_dates_csv,
                    ctx.usdm_csv,
                    ctx.overwrite,
                )
                report.built["gold"] = gold_report.get("status") in (None, "SUCCESS")
                log(f"[gold] status={gold_report.get('status')} weeks={gold_report.get('weeks')}")
            except Exception as exc:
                report.failures["gold"] = f"{type(exc).__name__}: {exc}"
                log(f"[gold] FAILED: {report.failures['gold']}")
    return report


def run(ctx: NoaaContext, log=logger.info) -> RunReport:
    """Plan and execute one NOAA medallion run."""
    report = plan(ctx)
    if report.ready and not ctx.dry_run:
        execute(ctx, report, log)
    return report
