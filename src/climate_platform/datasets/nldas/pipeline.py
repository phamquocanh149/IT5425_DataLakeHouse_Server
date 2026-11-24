"""NLDAS medallion orchestration: plan then execute Silver -> Gold per product.

One job: decide which reference weeks are buildable for each product (plan) and build the
missing Silver/Gold under the shared lock (execute). The per-product week lists live in
``RunReport.details['products']`` so the CLI keeps its original report shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from climate_platform.datasets.nldas import bronze, gate, paths, references
from climate_platform.datasets.nldas.complete import gold_complete_weeks, silver_complete_weeks
from climate_platform.datasets.nldas.gold import build_gold
from climate_platform.datasets.nldas.silver import build_silver
from climate_platform.medallion.contracts import RunReport
from climate_platform.medallion.runner import medallion_lock


@dataclass
class NldasContext:
    products: list
    bronze_root: Path
    references: Path
    silver_root: Path
    gold_root: Path
    start: Optional[date] = None
    end: Optional[date] = None
    keep_r25: bool = False
    lock_file: Path = field(default_factory=paths.default_lock_file)
    dry_run: bool = False


def default_context(product="both", **overrides) -> NldasContext:
    values = {
        "products": bronze.resolve_products(product),
        "bronze_root": paths.default_bronze_root(),
        "references": paths.default_references(),
        "silver_root": paths.default_silver_root(),
        "gold_root": paths.default_gold_root(),
    }
    values.update({key: value for key, value in overrides.items() if value is not None})
    return NldasContext(**values)


def _iso(weeks):
    return [week.isoformat() for week in sorted(weeks)]


def _empty_products(products, inventories):
    return {
        product: {
            "bronze_hours": len(inventories[product]),
            "ready_weeks": [],
            "planned_silver": [],
            "planned_gold": [],
            "built_silver": [],
            "built_gold": [],
        }
        for product in products
    }


def plan(ctx: NldasContext) -> RunReport:
    """Inspect Bronze/Silver/Gold and decide what a real run would build (no writes)."""
    readiness, ready, inventories = gate.check(ctx)

    report = RunReport(
        source="nldas",
        dry_run=ctx.dry_run,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        details={
            "bronze_root": str(Path(ctx.bronze_root).resolve()),
            "references": str(Path(ctx.references).resolve()),
            "silver_root": str(Path(ctx.silver_root).resolve()),
            "gold_root": str(Path(ctx.gold_root).resolve()),
            "products": _empty_products(ctx.products, inventories),
        },
    )
    for product in ctx.products:
        report.details["products"][product]["ready_weeks"] = _iso(ready[product])
    report.ready = readiness.ready
    report.reason = readiness.reason
    if not report.ready:
        return report

    grid_size = references.reference_grid_size(ctx.references)
    for product in ctx.products:
        silver_done = silver_complete_weeks(ctx.silver_root, product, grid_size=grid_size)
        gold_done = gold_complete_weeks(ctx.gold_root, product, grid_size=grid_size)
        report.details["products"][product]["planned_silver"] = _iso(
            set(ready[product]) - silver_done
        )
        report.details["products"][product]["planned_gold"] = _iso(set(ready[product]) - gold_done)

    report.planned = {
        "silver": any(report.details["products"][p]["planned_silver"] for p in ctx.products),
        "gold": any(report.details["products"][p]["planned_gold"] for p in ctx.products),
    }
    report.built = {"silver": False, "gold": False}
    report.skipped = {"silver": not report.planned["silver"], "gold": not report.planned["gold"]}
    return report


def execute(ctx: NldasContext, report: RunReport, log=print) -> RunReport:
    """Build missing Silver then Gold per product under the exclusive lock."""
    grid_size = references.reference_grid_size(ctx.references)
    ready = {
        product: [date.fromisoformat(day) for day in data["ready_weeks"]]
        for product, data in report.details["products"].items()
    }
    lock_message = f"NLDAS medallion already running (lock: {ctx.lock_file})"
    with medallion_lock(ctx.lock_file, lock_message):
        for product in ctx.products:
            data = report.details["products"][product]
            silver_plan = [date.fromisoformat(day) for day in data["planned_silver"]]
            try:
                if silver_plan:
                    build_silver(
                        product,
                        bronze_root=ctx.bronze_root,
                        references_dir=ctx.references,
                        silver_output=Path(ctx.silver_root) / product,
                        weeks=silver_plan,
                        log=log,
                    )
                silver_done = silver_complete_weeks(ctx.silver_root, product, grid_size=grid_size)
                data["built_silver"] = _iso([day for day in silver_plan if day in silver_done])
                gold_done_before = gold_complete_weeks(ctx.gold_root, product, grid_size=grid_size)
                gold_candidates = sorted((set(ready[product]) & silver_done) - gold_done_before)
                if gold_candidates:
                    build_gold(
                        product,
                        silver_input=Path(ctx.silver_root) / product,
                        references_dir=ctx.references,
                        gold_output=Path(ctx.gold_root) / product,
                        weeks=gold_candidates,
                        keep_r25=ctx.keep_r25,
                        log=log,
                    )
                gold_done = gold_complete_weeks(ctx.gold_root, product, grid_size=grid_size)
                data["built_gold"] = _iso([day for day in gold_candidates if day in gold_done])
            except Exception as exc:
                report.failures[product] = f"{type(exc).__name__}: {exc}"
                log(f"[{product}] failed: {report.failures[product]}")

    report.built = {
        "silver": any(report.details["products"][p]["built_silver"] for p in ctx.products),
        "gold": any(report.details["products"][p]["built_gold"] for p in ctx.products),
    }
    return report


def run(ctx: NldasContext, log=print) -> RunReport:
    report = plan(ctx)
    if report.ready and not ctx.dry_run:
        execute(ctx, report, log)
    return report
