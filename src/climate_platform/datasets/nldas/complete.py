"""NLDAS completeness checks for existing Silver/Gold outputs.

One job: answer "which weeks are already fully built?" so the runner can skip completed
work. Read-only over the Silver/Gold partitions.
"""

from __future__ import annotations

from pathlib import Path

from climate_platform.datasets.nldas.deps import require
from climate_platform.datasets.nldas.spec import VARIABLES


def silver_complete_weeks(silver_root, product, *, grid_size):
    """Weeks already present in Silver with a full grid and 168 valid hours."""
    require(["pandas", "pyarrow"], "Inspecting Silver")
    import pandas as pd

    complete = set()
    directory = Path(silver_root) / product
    columns = ["week_date", "quality_status"]
    columns += [f"{name}_valid_hours" for name in VARIABLES[product]]
    for path in sorted(directory.glob("year=*/data.parquet")):
        frame = pd.read_parquet(path, columns=columns)
        for week, chunk in frame.groupby("week_date"):
            if len(chunk) != grid_size:
                continue
            if not (chunk["quality_status"] == "complete").all():
                continue
            if all((chunk[f"{name}_valid_hours"] == 168).all() for name in VARIABLES[product]):
                complete.add(pd.Timestamp(week).date())
    return complete


def gold_complete_weeks(gold_root, product, *, grid_size):
    """Weeks already published to Gold with complete quality status."""
    require(["pandas", "pyarrow"], "Inspecting Gold")
    import pandas as pd

    complete = set()
    directory = Path(gold_root) / product
    for path in sorted(directory.glob("year=*/data.parquet")):
        frame = pd.read_parquet(path, columns=["week_date", "quality_status"])
        for week, chunk in frame.groupby("week_date"):
            if len(chunk) not in (grid_size, grid_size - 1):
                continue
            if (chunk["quality_status"] == "complete").all():
                complete.add(pd.Timestamp(week).date())
    return complete
