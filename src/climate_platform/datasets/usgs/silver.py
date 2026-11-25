"""USGS Bronze -> Silver science.

One job: map the grid to HUCs, align stations to grid cells and normalize each station's
daily discharge into Silver Parquet partitions, with the run report. No Gold logic, no lock.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from climate_platform.datasets.usgs.daily import clean_day, metadata, validate_daily
from climate_platform.datasets.usgs.grid_huc import map_grid, read_grid, read_huc
from climate_platform.datasets.usgs.manifest import inputs, save, stage
from climate_platform.datasets.usgs.paths import default_silver_root, job_path
from climate_platform.datasets.usgs.store import Store
from climate_platform.medallion.io import write_json_atomic


def station_alignment(stations, grid):
    rows = []
    xy = grid[["Lon", "Lat"]].to_numpy(float)
    for s in stations.itertuples():
        if pd.isna(s.lon) or pd.isna(s.lat):
            rows.append((s.site_id, None, None, False))
        else:
            d = np.abs(xy - [s.lon, s.lat]).sum(axis=1)
            idx = np.flatnonzero(d == d.min())
            rows.append((s.site_id, grid.grid_id.iloc[idx[0]], float(d[idx[0]]), len(idx) > 1))
    return pd.DataFrame(rows, columns=["site_id", "grid_id", "distance_degrees_l1", "tie"])


def silver(cfg, grid_path, wbd_path, silver_root=None):
    root = Path(cfg.output)
    silver_root = Path(silver_root) if silver_root else default_silver_root()
    for source in (grid_path, wbd_path):
        if not source.is_file():
            raise FileNotFoundError(f"Required input missing: {source}")
    grid = read_grid(grid_path, "grid_id", "lon", "lat")
    wbd, crs = read_huc(wbd_path, "WBDHU8", "huc8")
    mapped = map_grid(grid, wbd)
    catalog = json.loads((root / "catalog.json").read_text())
    sites = sorted({r["site_id"] for r in catalog if r["decision"] == "included"})
    meta, issues = metadata(catalog, sites)
    stations = pd.DataFrame(
        [
            {
                "site_id": s,
                "lon": meta[s]["coordinates"][0] if meta[s]["coordinates"] else None,
                "lat": meta[s]["coordinates"][1] if meta[s]["coordinates"] else None,
                **{f"huc{k}": v for k, v in meta[s]["hucs"].items()},
            }
            for s in sites
        ]
    )
    store = Store(cfg)
    try:
        jobs = list(store.db.execute("SELECT * FROM jobs ORDER BY site,year"))
        with stage(silver_root, "silver", [root / "catalog.json", grid_path, wbd_path]) as (run, m):
            m["config"] = asdict(cfg)
            provenance = [
                grid_path.with_suffix(".source.json"),
                wbd_path.parent / "wbd_source.json",
            ]
            m["sources"].extend(inputs([p for p in provenance if p.is_file()]))
            m["sources"].extend(inputs(sorted((root / "raw").rglob("*.json.gz"))))
            save(stations, run / "stations.parquet")
            save(grid, run / "grid.parquet")
            save(mapped, run / "grid_huc.parquet")
            save(station_alignment(stations, grid), run / "station_grid.parquet")
            save(mapped[mapped.huc8.isna()], run / "review_unresolved.parquet")
            counts = Counter()
            daily_rows = 0
            valid_rows = 0
            # Bronze remains immutable; catalog, raw sidecars and normalized files are referenced.
            bronze = inputs(sorted((root / "raw").rglob("*.meta.json")))
            m["sources"].extend(bronze)
            write_json_atomic(
                run / "bronze_manifest.json",
                {
                    "raw_sidecars": bronze,
                    "raw_audit": json.loads((root / "reports/raw_audit.json").read_text()),
                },
            )
            for j in jobs:
                source = job_path(root, j)
                m["sources"].extend(inputs([source]))
                groups = {}
                for r in pq.ParquetFile(source).read().to_pylist():
                    groups.setdefault(r["date"], []).append(r)
                rows = [
                    clean_day(j["site"], t.date().isoformat(), groups.get(t.date().isoformat(), []))
                    for t in pd.date_range(j["start"], j["end"])
                ]
                df = pd.DataFrame(rows)
                df["unit"] = "cfs"
                validate_daily(df, j["site"], j["start"], j["end"], check_qc=True)
                daily_rows += len(df)
                valid_rows += int(df.discharge_cfs.notna().sum())
                counts.update(flag for row in rows for flag in row["qc_flags"])
                save(
                    df,
                    run
                    / "station_daily"
                    / f"region={j['region']}"
                    / f"year={j['year']}"
                    / f"{j['site']}.parquet",
                )
            write_json_atomic(
                run / "report.json",
                {
                    "passed": True,
                    "daily_rows": daily_rows,
                    "valid_daily_rows": valid_rows,
                    "missing_daily_rows": daily_rows - valid_rows,
                    "filled_values": 0,
                    "stations": len(stations),
                    "grid_cells": len(grid),
                    "unresolved_grid_huc": int(mapped.huc8.isna().sum()),
                    "metadata_issues": issues,
                    "qc_counts": dict(counts),
                    "wbd_crs": crs,
                },
            )
        return run
    finally:
        store.close()
