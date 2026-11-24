#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification Script: Silver-to-Gold Concordance & USDM Alignment Verifier
=========================================================================
Independently recomputes weekly NOAA Gold features from Silver Parquet tables
and verifies 100% numeric & temporal concordance against Gold climate_weekly
outputs (Parquet + CSV) and the 130-week USDM Tuesday reference calendar.

Also supports inspecting specific weeks (default: first, mid, last USDM weeks)
and exporting data_lake/gold/noaa/comparison_reports/verification_summary.json.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from climate_platform.datasets.noaa.paths import (  # noqa: E402
    gold_root as default_gold_root,
    silver_root as default_silver_root,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
)
logger = logging.getLogger("NOAA_SilverToGoldVerifier")

VALUE_COLUMNS = ["ao", "nao", "pna", "enso", "enso14", "enso28", "enso84"]


def recompute_from_silver(
    daily: pd.DataFrame, enso: pd.DataFrame, weeks: pd.DatetimeIndex
) -> pd.DataFrame:
    """Independent reference implementation of TeleconnectionsForDryad.R aggregation."""
    daily_idx = daily.copy()
    daily_idx["date"] = pd.to_datetime(daily_idx["date"]).astype("datetime64[ns]")
    daily_idx = daily_idx.set_index("date").sort_index()

    enso_idx = enso.copy()
    enso_idx["source_week_date"] = pd.to_datetime(enso_idx["source_week_date"]).astype(
        "datetime64[ns]"
    )
    enso_idx = enso_idx.set_index("source_week_date").sort_index()

    rows: List[Dict[str, Any]] = []
    for week in weeks:
        # 7 days ending on USDM Tuesday (inclusive): [week - 6 days, week]
        d_win = daily_idx.loc[week - pd.Timedelta(days=6) : week]
        if len(d_win) != 7:
            raise ValueError(f"Incomplete 7-day window for {week.date()}: {len(d_win)} rows")

        # ENSO Wednesday = USDM Tuesday + 1 day
        wed = week + pd.Timedelta(days=1)
        if wed not in enso_idx.index:
            raise ValueError(f"Missing ENSO Wednesday {wed.date()} for USDM week {week.date()}")

        pos = enso_idx.index.get_loc(wed)
        if pos < 11:
            raise ValueError(f"Insufficient ENSO history before {wed.date()} for 12-week enso84")

        ssta = enso_idx["nino34_ssta"]
        rows.append(
            {
                "week_date": week,
                "ao": round(float(d_win["ao"].mean()), 2),
                "nao": round(float(d_win["nao"].mean()), 2),
                "pna": round(float(d_win["pna"].mean()), 2),
                "enso": round(float(ssta.iloc[pos]), 2),
                "enso14": round(float(ssta.iloc[pos - 1 : pos + 1].mean()), 3),
                "enso28": round(float(ssta.iloc[pos - 3 : pos + 1].mean()), 3),
                "enso84": round(float(ssta.iloc[pos - 11 : pos + 1].mean()), 3),
            }
        )

    out = pd.DataFrame(rows)
    out["week_date"] = pd.to_datetime(out["week_date"]).astype("datetime64[ns]")
    return out


def verify(
    silver_root: Path,
    gold_root: Path,
    sample_weeks: List[str],
    usdm_csv: Path | None = None,
) -> Dict[str, Any]:
    daily = pd.read_parquet(silver_root / "climate_daily.parquet")
    enso = pd.read_parquet(silver_root / "enso_weekly.parquet")
    gold_pq = pd.read_parquet(gold_root / "climate_weekly.parquet")
    gold_pq["week_date"] = pd.to_datetime(gold_pq["week_date"]).astype("datetime64[ns]")

    week_dates_path = gold_root / "usdm_week_dates.csv"
    ref_weeks = pd.DatetimeIndex(
        pd.to_datetime(pd.read_csv(week_dates_path)["week_date"], format="%Y-%m-%d")
    ).astype("datetime64[ns]")

    recomputed = recompute_from_silver(daily, enso, ref_weeks)

    # 1. Parquet comparison
    calendar_match = pd.DatetimeIndex(gold_pq["week_date"]).equals(ref_weeks)
    all_tuesdays = bool((gold_pq["week_date"].dt.dayofweek == 1).all())
    null_count = int(gold_pq.isna().sum().sum())
    dup_count = int(gold_pq["week_date"].duplicated().sum())

    max_abs_diff: Dict[str, float] = {}
    exact_matches_per_col: Dict[str, int] = {}
    for col in VALUE_COLUMNS:
        diffs = np.abs(gold_pq[col].to_numpy(dtype=float) - recomputed[col].to_numpy(dtype=float))
        max_abs_diff[col] = float(np.max(diffs))
        exact_matches_per_col[col] = int(np.sum(diffs < 1e-12))

    total_cells = len(ref_weeks) * len(VALUE_COLUMNS)
    matched_cells = sum(exact_matches_per_col.values())
    concordance_pct = round(matched_cells / total_cells * 100.0, 4)

    # 2. CSV parity check if climate_weekly.csv exists
    csv_path = gold_root / "climate_weekly.csv"
    csv_parity = None
    if csv_path.exists():
        gold_csv = pd.read_csv(csv_path)
        gold_csv["week_date"] = pd.to_datetime(gold_csv["week_date"]).astype("datetime64[ns]")
        csv_parity = bool(
            pd.DatetimeIndex(gold_csv["week_date"]).equals(pd.DatetimeIndex(gold_pq["week_date"]))
            and all(
                np.allclose(
                    gold_csv[c].to_numpy(dtype=float), gold_pq[c].to_numpy(dtype=float), atol=1e-12
                )
                for c in VALUE_COLUMNS
            )
        )

    # 3. Optional USDM usdmfinal.csv calendar check
    usdm_csv_match = None
    if usdm_csv is not None and usdm_csv.exists():
        usdm_times = set()
        for chunk in pd.read_csv(
            usdm_csv, usecols=["time"], dtype={"time": str}, chunksize=100_000
        ):
            usdm_times.update(chunk["time"].tolist())
        usdm_dt = pd.DatetimeIndex(pd.to_datetime(sorted(usdm_times), format="%Y%m%d")).astype(
            "datetime64[ns]"
        )
        usdm_csv_match = bool(pd.DatetimeIndex(gold_pq["week_date"]).equals(usdm_dt))

    # 4. Sample week breakdown
    sample_checks = []
    for raw_w in sample_weeks:
        w_iso = (
            f"{raw_w[:4]}-{raw_w[4:6]}-{raw_w[6:]}"
            if len(raw_w) == 8 and "-" not in raw_w
            else raw_w
        )
        ts = pd.Timestamp(w_iso)
        g_row = gold_pq[gold_pq["week_date"] == ts]
        r_row = recomputed[recomputed["week_date"] == ts]
        if g_row.empty or r_row.empty:
            sample_checks.append({"week_date": w_iso, "status": "NOT_FOUND"})
            continue
        diffs = {c: float(abs(g_row.iloc[0][c] - r_row.iloc[0][c])) for c in VALUE_COLUMNS}
        sample_checks.append(
            {
                "week_date": w_iso,
                "enso_source_week_date": str((ts + pd.Timedelta(days=1)).date()),
                "status": "MATCH" if max(diffs.values()) < 1e-12 else "MISMATCH",
                "values": {c: float(g_row.iloc[0][c]) for c in VALUE_COLUMNS},
                "max_abs_diff": max(diffs.values()),
            }
        )

    passed = (
        calendar_match
        and all_tuesdays
        and null_count == 0
        and dup_count == 0
        and matched_cells == total_cells
        and (csv_parity in (True, None))
        and (usdm_csv_match in (True, None))
    )

    summary = {
        "verified_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "weeks_evaluated": len(ref_weeks),
        "week_range": f"{ref_weeks.min().date()} .. {ref_weeks.max().date()}",
        "calendar_match_usdm_week_dates": calendar_match,
        "calendar_match_usdmfinal_csv": usdm_csv_match,
        "all_tuesdays": all_tuesdays,
        "null_values": null_count,
        "duplicate_weeks": dup_count,
        "total_numeric_cells": total_cells,
        "exact_matched_cells": matched_cells,
        "concordance_percentage": concordance_pct,
        "parquet_csv_parity": csv_parity,
        "max_abs_diff_by_column": max_abs_diff,
        "sample_week_checks": sample_checks,
    }

    report_dir = gold_root / "comparison_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "verification_summary.json"
    report_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    logger.info(f"Verification summary saved to: {report_path}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify 100% Silver-to-Gold reproduction for NOAA Teleconnections."
    )
    parser.add_argument(
        "--silver-root",
        type=Path,
        default=default_silver_root(),
        help="Path to Silver data directory.",
    )
    parser.add_argument(
        "--gold-root",
        type=Path,
        default=default_gold_root(),
        help="Path to Gold data directory.",
    )
    parser.add_argument(
        "--usdm-csv",
        type=Path,
        default=None,
        help="Optional path to USDM Gold usdmfinal.csv for cross-repo calendar check.",
    )
    parser.add_argument(
        "--weeks",
        nargs="+",
        default=["20200107", "20210601", "20220628"],
        help="Sample weeks to print detailed verification (YYYYMMDD or YYYY-MM-DD).",
    )
    args = parser.parse_args()

    summary = verify(args.silver_root, args.gold_root, args.weeks, args.usdm_csv)
    print("\n=== Silver -> Gold Verification Summary ===")
    print(f"  Status                 : {summary['status']}")
    print(f"  Weeks evaluated        : {summary['weeks_evaluated']} ({summary['week_range']})")
    print(
        f"  Concordance            : {summary['exact_matched_cells']}/{summary['total_numeric_cells']} ({summary['concordance_percentage']}%)"
    )
    print(f"  Parquet/CSV parity     : {summary['parquet_csv_parity']}")
    print(f"  USDM week calendar     : {summary['calendar_match_usdm_week_dates']}")
    if summary["calendar_match_usdmfinal_csv"] is not None:
        print(f"  USDM usdmfinal.csv     : {summary['calendar_match_usdmfinal_csv']}")
    for sc in summary["sample_week_checks"]:
        print(
            f"\n--- Sample Week {sc['week_date']} (ENSO Wed: {sc.get('enso_source_week_date')}) ---"
        )
        print(f"  status       : {sc['status']}")
        print(f"  max_abs_diff : {sc.get('max_abs_diff')}")
        print(f"  values       : {sc.get('values')}")

    if summary["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
