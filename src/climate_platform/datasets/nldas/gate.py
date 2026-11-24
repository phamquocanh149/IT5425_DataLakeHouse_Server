"""NLDAS eligibility gate.

One job: decide which reference weeks are complete in Bronze for each product, and whether
any work is eligible at all. Reads Bronze only; never writes.
"""

from __future__ import annotations

from pathlib import Path

from climate_platform.datasets.nldas import bronze
from climate_platform.medallion.contracts import Readiness


def check(ctx):
    """Return ``(Readiness, ready_by_product, inventories)`` for the context's weeks."""
    dates = bronze.load_week_dates(Path(ctx.references) / "week_dates.csv")
    if ctx.start:
        dates = [day for day in dates if day >= ctx.start]
    if ctx.end:
        dates = [day for day in dates if day <= ctx.end]
    inventories = {product: bronze.inventory(ctx.bronze_root, product) for product in ctx.products}
    ready = bronze.ready_weeks(dates, inventories)
    if not any(ready.values()):
        return Readiness(False, "no complete reference weeks in Bronze"), ready, inventories
    return Readiness(True, ""), ready, inventories
