"""NLDAS Bronze inventory and readiness math.

One job: locate the hourly NetCDF files and decide which reference weeks are complete (all
168 hours present) and which reference calendar dates to consider. Read-only over Bronze.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, time, timedelta
from pathlib import Path

from climate_platform.datasets.nldas.spec import PRODUCTS


def resolve_products(value):
    if value.lower() == "both":
        return list(PRODUCTS)
    product = value.upper()
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {value}")
    return [product]


def file_pattern(product):
    """Match the NLDAS hourly filename used by the crawl engine."""
    return re.compile(r"nldas_" + product.lower() + r"0125_h\.a(\d{8})\.(\d{4})", re.I)


def inventory(directory, product):
    """Return ``{datetime: Path}`` for every NLDAS hour under ``directory``."""
    pattern = file_pattern(product)
    records = {}
    for path in sorted(Path(directory).rglob("*.nc")):
        match = pattern.search(path.name)
        if not match:
            continue
        stamp = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M")
        if stamp in records:
            raise ValueError(f"Duplicate {product} timestamp {stamp}: {records[stamp]} and {path}")
        records[stamp] = path
    return records


def week_hours(week_date):
    """The 168 source hours ending at ``week_date`` (Tuesday) 00:00."""
    end = datetime.combine(week_date, time.min)
    return [end - timedelta(hours=168 - index) for index in range(168)]


def missing_hours(week_date, records):
    return [hour for hour in week_hours(week_date) if hour not in records]


def ready_weeks(dates, inventories):
    """Per product, reference weeks whose 168 hours are all present in Bronze."""
    ready = {product: [] for product in inventories}
    for week_date in dates:
        hours = week_hours(week_date)
        for product, records in inventories.items():
            if all(hour in records for hour in hours):
                ready[product].append(week_date)
    return ready


def load_week_dates(path):
    """Read the reference Tuesday calendar without requiring pandas."""
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or "week_date" not in rows[0]:
        raise ValueError(f"Expected a week_date column in {path}")
    dates = [datetime.strptime(row["week_date"], "%Y-%m-%d").date() for row in rows]
    if len(set(dates)) != len(dates):
        raise ValueError("Reference week dates are duplicated")
    if dates != sorted(dates):
        raise ValueError("Reference week dates must increase")
    if any(day.weekday() != 1 for day in dates):
        raise ValueError("Reference week dates must be Tuesdays")
    return dates
