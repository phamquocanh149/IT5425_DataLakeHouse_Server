"""USGS Weekly -> Gold builder.

One job: aggregate the per-station weekly percentiles onto every grid cell and write the Gold
partitions, then fail closed by validating them (validation lives in ``gold_validate``). No
lock, no orchestration.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from climate_platform.datasets.usgs.aggregate import aggregate_week
from climate_platform.datasets.usgs.gold_validate import validate_gold
from climate_platform.datasets.usgs.manifest import read, save, stage, verified
from climate_platform.datasets.usgs.paths import default_gold_root
from climate_platform.medallion.io import write_json_atomic


def gold(weekly_run):
    wm = verified(weekly_run, expected_stage="weekly")
    sr = Path(wm["silver_run"])
    verified(sr, expected_stage="silver")
    grid, mapped, stations, alignment = [
        read(sr / f"{name}.parquet") for name in ["grid", "grid_huc", "stations", "station_grid"]
    ]
    with stage(
        default_gold_root(), "gold", [weekly_run / "manifest.json", sr / "manifest.json"]
    ) as (
        run,
        m,
    ):
        m.update(silver_run=str(sr.resolve()), weekly_run=str(weekly_run.resolve()))
        write_json_atomic(run / "manifest.json", m)
        for year in (2020, 2021, 2022):
            allweeks = pd.concat(
                [
                    read(p)
                    for p in sorted(
                        (weekly_run / "station_weekly" / f"year={year}").glob("*.parquet")
                    )
                ],
                ignore_index=True,
            )
            for day, week in allweeks.groupby("week_date", sort=True):
                df, trace = aggregate_week(grid, mapped, stations, alignment, week, run.name)
                filename = f"{day:%Y%m%d}.parquet"
                save(df, run / "grid_weekly" / f"year={year}" / filename)
                save(trace, run / "lineage" / f"year={year}" / filename)
            print(f"Gold {year} complete", flush=True)
        report = validate_gold(run, check_manifest=False)
        write_json_atomic(run / "report.json", report)
        if not report["passed"]:
            raise ValueError(report)
    return run
