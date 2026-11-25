"""USGS Silver -> Weekly science.

One job: compute each station's trailing-window discharge means and percentile ranks for
every baseline Tuesday, writing the Weekly Parquet partitions. No Gold logic, no lock.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from climate_platform.datasets.usgs.daily import validate_daily
from climate_platform.datasets.usgs.manifest import read, save, stage, verified
from climate_platform.datasets.usgs.method import METHOD, WINDOWS
from climate_platform.datasets.usgs.paths import default_silver_root
from climate_platform.medallion.io import file_hash, write_json_atomic


def percentile_rank(values):
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    valid = np.isfinite(values)
    ordered = np.sort(values[valid])
    n = len(ordered)
    if n:
        q = values[valid]
        left = np.searchsorted(ordered, q, "left")
        right = np.searchsorted(ordered, q, "right")
        multiplicity = right - left
        position = left + np.where(multiplicity < 3, 1, (multiplicity + 1) // 2)
        out[valid] = 100 * position / n
    return out


def weekly_station(daily, site):
    start, end = METHOD["baseline_start"], METHOD["baseline_end"]
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily.date)
    if daily.date.duplicated().any():
        raise ValueError("Duplicate station/day")
    series = daily.set_index("date").discharge_cfs.reindex(pd.date_range(start, end)).astype(float)
    dates = pd.date_range(start, end, freq="W-TUE")
    result = pd.DataFrame({"site_id": site, "week_date": dates})
    for w in WINDOWS:
        count = series.shift(1).rolling(w, min_periods=1).count().reindex(dates).fillna(0)
        q = series.shift(1).rolling(w, min_periods=METHOD["min_days"][str(w)]).mean().reindex(dates)
        q.loc[dates - pd.Timedelta(days=w) < pd.Timestamp(start)] = np.nan
        result[f"q{w}"] = q.to_numpy()
        result[f"p{w}"] = percentile_rank(q.to_numpy())
        result[f"n_days{w}"] = count.to_numpy(dtype=int)
        result[f"n_baseline{w}"] = int(q.notna().sum())
        result[f"reason{w}"] = np.where(
            dates - pd.Timedelta(days=w) < pd.Timestamp(start),
            "window_before_start",
            np.where(q.isna(), "insufficient_valid_days", "ok"),
        )
    return result


def weekly(silver_run, silver_root=None):
    verified(silver_run, expected_stage="silver")
    silver_root = Path(silver_root) if silver_root else default_silver_root()
    with stage(silver_root, "weekly", [silver_run / "manifest.json"]) as (run, m):
        m["silver_run"] = str(silver_run.resolve())
        stations = read(silver_run / "stations.parquet")
        files = {}
        for p in (silver_run / "station_daily").rglob("*.parquet"):
            files.setdefault(p.stem, []).append(p)
        coverage = []
        for site in stations.site_id:
            daily = pd.concat([read(p) for p in files[site]], ignore_index=True)
            validate_daily(daily, site, METHOD["baseline_start"], METHOD["baseline_end"])
            df = weekly_station(daily, site)
            coverage.append(
                {
                    "site_id": site,
                    **{f"n_baseline{w}": int(df[f"n_baseline{w}"].iloc[0]) for w in WINDOWS},
                }
            )
            for year, group in df.groupby(df.week_date.dt.year):
                save(group, run / "station_weekly" / f"year={year}" / f"{site}.parquet")
        save(pd.DataFrame(coverage), run / "baseline_coverage.parquet")
        write_json_atomic(
            run / "report.json",
            {
                "passed": True,
                "stations": len(stations),
                "weeks_per_station": len(
                    pd.date_range(METHOD["baseline_start"], METHOD["baseline_end"], freq="W-TUE")
                ),
                "baseline": METHOD,
                "silver_manifest_sha256": file_hash(silver_run / "manifest.json"),
            },
        )
    return run
