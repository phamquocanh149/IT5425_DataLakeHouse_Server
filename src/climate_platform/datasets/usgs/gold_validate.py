"""USGS Gold validation: independently recompute and verify every Gold partition.

One job: check the built Gold against the upstream Weekly/Silver inputs, lineage and the
Tuesday calendar. It never builds Gold; the builder calls it to fail closed before the run
manifest is marked complete.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from climate_platform.datasets.usgs.aggregate import aggregate_week
from climate_platform.datasets.usgs.manifest import read, verified
from climate_platform.datasets.usgs.method import METHOD, WINDOWS
from climate_platform.datasets.usgs.paths import default_bronze_root


def validate_gold(run, check_manifest=True):
    if check_manifest:
        verified(run, expected_stage="gold")
    m = json.loads((run / "manifest.json").read_text())
    sr = Path(m["silver_run"])
    grid = read(sr / "grid.parquet")
    station_meta = read(sr / "stations.parquet").set_index("site_id")
    aligned = read(sr / "station_grid.parquet").set_index("site_id")
    grid_meta = read(sr / "grid_huc.parquet").set_index("grid_id")
    grid_xy = grid.set_index("grid_id")
    weekly_run = Path(m["weekly_run"])
    cached_year = None
    station_records = station_meta.to_dict("index")
    aligned_records = aligned.grid_id.to_dict()
    grid_records = grid_meta.to_dict("index")
    xy_records = grid_xy.to_dict("index")
    expected_dates = set(
        pd.date_range(METHOD["baseline_start"], METHOD["baseline_end"], freq="W-TUE")
    )
    dates = set()
    rows = 0
    coverage = Counter()
    problems = []
    donor_histograms = {}
    for p in sorted((run / "grid_weekly").rglob("*.parquet")):
        df = read(p)
        if df.empty:
            problems.append(f"Empty Gold partition: {p}")
            continue
        day = pd.Timestamp(df.week_date.iloc[0])
        if cached_year != day.year:
            cached_year = day.year
            weekly_sources = pd.concat(
                [
                    read(f)
                    for f in sorted(
                        (weekly_run / "station_weekly" / f"year={day.year}").glob("*.parquet")
                    )
                ],
                ignore_index=True,
            )
            if weekly_sources.duplicated(["site_id", "week_date"]).any():
                raise ValueError("Duplicate upstream station/week")
            weekly_sources = weekly_sources.set_index(["week_date", "site_id"])
        if (
            day in dates
            or set(df.week_date) != {day}
            or set(df.grid_id) != set(grid.grid_id)
            or df.grid_id.duplicated().any()
        ):
            problems.append(str(p))
        dates.add(day)
        rows += len(df)
        for c in df.columns:
            if c.startswith(("n_donors_", "n_stations")):
                hist = donor_histograms.setdefault(c, Counter())
                hist.update(int(n) for n in df[c])
            if c in ["p7", "p14", "p28"] or c.startswith(("mean_", "idw_")):
                v = df[c].dropna().astype(float)
                if not np.isfinite(v).all() or not v.between(-1e-10, 100 + 1e-10).all():
                    problems.append(c)
                coverage[c] += len(v)
        observations = weekly_sources.xs(day).reset_index().assign(week_date=day)
        expected, _ = aggregate_week(
            grid,
            grid_meta.reset_index(),
            station_meta.reset_index(),
            aligned.reset_index(),
            observations,
            run.name,
        )
        try:
            pd.testing.assert_frame_equal(
                df.sort_values("grid_id").reset_index(drop=True),
                expected.sort_values("grid_id").reset_index(drop=True),
                check_dtype=False,
                check_like=True,
                check_exact=False,
                rtol=1e-10,
                atol=1e-10,
            )
        except AssertionError:
            problems.append(f"Gold differs from upstream aggregation: {day.date()}")
        source_records = weekly_sources.xs(day).to_dict("index")
        trace = read(run / "lineage" / p.parent.name / p.name)
        trace_counts = Counter((r.grid_id, r.window, r.level) for r in trace.itertuples())
        lookup = df.set_index("grid_id").to_dict("index")
        for r in trace.itertuples():
            c = f"n_stations{r.window}" if r.level == 0 else f"n_donors_huc{r.level}_{r.window}"
            if (
                lookup[r.grid_id][c] != len(r.site_ids)
                or len(r.site_ids) != len(set(r.site_ids))
                or len(r.site_ids) != len(r.percentiles)
            ):
                problems.append("lineage count")
            if pd.Timestamp(r.week_date) != day:
                problems.append("lineage date")
            if any(
                site not in station_records or site not in source_records for site in r.site_ids
            ):
                problems.append("unknown donor")
                continue
            source_values = np.array(
                [source_records[site][f"p{r.window}"] for site in r.site_ids], dtype=float
            )
            if (
                len(source_values) != len(r.percentiles)
                or not np.isfinite(source_values).all()
                or not np.allclose(source_values, r.percentiles)
            ):
                problems.append("donor differs from station percentile")
            if r.level == 0:
                if any(aligned_records[site] != r.grid_id for site in r.site_ids):
                    problems.append("wrong direct grid")
            else:
                code = grid_records[r.grid_id][f"huc{r.level}"]
                station_codes = [station_records[site][f"huc{r.level}"] for site in r.site_ids]
                if pd.isna(code) or any(pd.isna(c) or c != code for c in station_codes):
                    problems.append("wrong donor HUC")
                if pd.notna(lookup[r.grid_id][f"p{r.window}"]):
                    problems.append("filled direct value")
                distances = np.hypot(
                    np.array([station_records[site]["lon"] for site in r.site_ids])
                    - xy_records[r.grid_id]["Lon"],
                    np.array([station_records[site]["lat"] for site in r.site_ids])
                    - xy_records[r.grid_id]["Lat"],
                )
                if len(distances) != len(r.distances_degrees) or not np.allclose(
                    distances, r.distances_degrees
                ):
                    problems.append("donor distance mismatch")
            vals = np.asarray(r.percentiles, dtype=float)
            if not np.isfinite(vals).all() or ((vals < 0) | (vals > 100)).any():
                problems.append("invalid donor percentile")
            value_col = f"p{r.window}" if r.level == 0 else f"mean_huc{r.level}_{r.window}"
            if not np.isclose(lookup[r.grid_id][value_col], vals.mean()):
                problems.append("mean mismatch")
            if r.level:
                d = np.asarray(r.distances_degrees, dtype=float)
                if len(d) != len(vals) or not np.isfinite(d).all() or (d < 0).any():
                    problems.append("invalid distance")
                else:
                    expected_idw = (
                        vals[d == 0].mean() if (d == 0).any() else np.average(vals, weights=1 / d)
                    )
                    if not np.isclose(
                        lookup[r.grid_id][f"idw_huc{r.level}_{r.window}"], expected_idw
                    ):
                        problems.append("IDW mismatch")
        for r in df.itertuples():
            for w in WINDOWS:
                for level in (0, 8, 6, 4):
                    c = f"n_stations{w}" if level == 0 else f"n_donors_huc{level}_{w}"
                    expected = int(getattr(r, c))
                    # Positive counts require exactly one trace record.
                    if expected and trace_counts[(r.grid_id, w, level)] != 1:
                        problems.append("missing lineage")
    if dates != expected_dates:
        problems.append("incomplete Tuesday calendar")
    silver_manifest = json.loads((sr / "manifest.json").read_text())
    source_root = Path(silver_manifest.get("config", {}).get("output", default_bronze_root()))
    manual_path = source_root / "reports/manual_comparison.json"
    manual_ok = manual_path.is_file() and bool(json.loads(manual_path.read_text()).get("passed"))
    return {
        "passed": not problems,
        "issues": problems[:100],
        "rows": rows,
        "weeks": len(dates),
        "grid_cells": len(grid),
        "coverage": dict(coverage),
        "donor_count_histograms": donor_histograms,
        "manual_comparison_completed": manual_ok,
        "acceptance_status": "complete"
        if not problems and manual_ok
        else "automated_checks_only"
        if not problems
        else "failed",
        "purpose": METHOD["purpose"],
    }
