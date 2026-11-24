"""USGS Weekly -> Gold grid aggregation (pure science).

One job: aggregate per-station weekly percentiles onto every grid cell (direct, then HUC-8/6/4
donors with mean and IDW). Shared by the Gold builder and the Gold validator so neither
imports the other. No IO, no lock.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from climate_platform.datasets.usgs.method import WINDOWS


def aggregate_week(grid, mapped, stations, alignment, observations, run_id):
    merged = observations.merge(stations, on="site_id", validate="one_to_one").merge(
        alignment[["site_id", "grid_id"]], on="site_id", validate="one_to_one"
    )
    output, lineage = [], []

    def pack(frame, w):
        return (
            frame.site_id.tolist(),
            frame[f"p{w}"].to_numpy(float),
            frame.lon.to_numpy(float),
            frame.lat.to_numpy(float),
        )

    direct_pools = {
        (w, code): pack(g, w)
        for w in WINDOWS
        for code, g in merged[merged[f"p{w}"].notna()].groupby("grid_id")
    }
    hucs = mapped.set_index("grid_id").to_dict("index")
    pools = {
        (w, level, code): pack(g, w)
        for w in WINDOWS
        for level in (8, 6, 4)
        for code, g in merged[
            merged[f"p{w}"].notna() & merged.lon.notna() & merged.lat.notna()
        ].groupby(f"huc{level}")
    }
    day = observations.week_date.iloc[0]
    for cell in grid.itertuples():
        row = {"grid_id": cell.grid_id, "week_date": day, "run_id": run_id}
        for w in WINDOWS:
            obs = direct_pools.get((w, cell.grid_id))
            nobs = len(obs[0]) if obs is not None else 0
            row[f"p{w}"] = float(obs[1].mean()) if nobs else None
            row[f"n_stations{w}"] = nobs
            row[f"reason{w}"] = "direct" if nobs else "no_valid_station"
            if nobs:
                lineage.append(
                    {
                        "grid_id": cell.grid_id,
                        "week_date": day,
                        "window": w,
                        "level": 0,
                        "site_ids": obs[0],
                        "percentiles": obs[1].tolist(),
                        "distances_degrees": [],
                    }
                )
            for level in (8, 6, 4):
                key = f"huc{level}_{w}"
                code = hucs[cell.grid_id][f"huc{level}"]
                pool = pools.get((w, level, code)) if pd.notna(code) and not nobs else None
                row[f"mean_{key}"] = row[f"idw_{key}"] = None
                row[f"n_donors_{key}"] = 0
                row[f"reason_{key}"] = (
                    "direct_available"
                    if nobs
                    else "missing_huc"
                    if pd.isna(code)
                    else "no_valid_donors"
                )
                if pool is not None:
                    distances = np.hypot(pool[2] - cell.Lon, pool[3] - cell.Lat)
                    values = pool[1]
                    zero = distances == 0
                    row[f"mean_{key}"] = float(values.mean())
                    row[f"idw_{key}"] = float(
                        values[zero].mean()
                        if zero.any()
                        else np.average(values, weights=1 / distances)
                    )
                    row[f"n_donors_{key}"] = len(pool[0])
                    row[f"reason_{key}"] = "ok"
                    lineage.append(
                        {
                            "grid_id": cell.grid_id,
                            "week_date": day,
                            "window": w,
                            "level": level,
                            "site_ids": pool[0],
                            "percentiles": values.tolist(),
                            "distances_degrees": distances.tolist(),
                        }
                    )
        output.append(row)
    return pd.DataFrame(output), pd.DataFrame(
        lineage,
        columns=[
            "grid_id",
            "week_date",
            "window",
            "level",
            "site_ids",
            "percentiles",
            "distances_degrees",
        ],
    )
