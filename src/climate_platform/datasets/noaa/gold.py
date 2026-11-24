"""NOAA Silver -> Gold science.

One job: aggregate the Silver daily/weekly tables into the curated ML-ready Gold
``climate_weekly`` table (AO/NAO/PNA 7-day rolling means ending on the USDM Tuesday, ENSO
SSTA windows), and write the validation/lineage/environment artifacts. No orchestration.
"""

from __future__ import annotations

import csv
import datetime
import logging
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa

from climate_platform.datasets.noaa import paths, spec
from climate_platform.datasets.noaa.validation import validate_table
from climate_platform.medallion.io import (
    atomic_write,
    file_hash,
    outputs_complete,
    write_completion_marker,
    write_text_atomic,
)

logger = logging.getLogger("climate_platform.noaa")


def read_usdm_weeks(path: Path) -> pd.DatetimeIndex:
    """Extract unique USDM Tuesday dates from usdmfinal.csv (YYYYMMDD)."""
    dates = set()
    for chunk in pd.read_csv(path, usecols=["time"], dtype={"time": "string"}, chunksize=100_000):
        if chunk["time"].isna().any() or not chunk["time"].str.fullmatch(r"\d{8}").all():
            raise ValueError("USDM time must contain YYYYMMDD dates without missing values")
        dates.update(chunk["time"].tolist())
    weeks = pd.DatetimeIndex(pd.to_datetime(sorted(dates), format="%Y%m%d")).astype(
        "datetime64[ns]"
    )
    if weeks.empty or not (weeks.dayofweek == 1).all():
        raise ValueError("Expected nonempty USDM Tuesday dates")
    return weeks


def read_week_dates(path: Path) -> pd.DatetimeIndex:
    """Read the USDM Tuesday reference calendar from usdm_week_dates.csv."""
    weeks = pd.DatetimeIndex(
        pd.to_datetime(pd.read_csv(path)["week_date"], format="%Y-%m-%d")
    ).astype("datetime64[ns]")
    if weeks.empty or weeks.duplicated().any() or not (weeks.dayofweek == 1).all():
        raise ValueError("Expected nonempty, unique Tuesday dates in column week_date")
    return weeks.sort_values()


def build_gold(daily: pd.DataFrame, enso: pd.DataFrame, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """Aggregate Silver daily/weekly tables into the curated Gold climate_weekly table."""
    weeks = pd.DatetimeIndex(pd.to_datetime(weeks)).astype("datetime64[ns]")
    daily_clean = validate_table(daily[["date", "ao", "nao", "pna"]], "date", "D").set_index("date")
    enso_clean = validate_table(
        enso[["source_week_date", "nino34_sst", "nino34_ssta"]],
        "source_week_date",
        "7D",
    ).set_index("source_week_date")

    if not (enso_clean.index.dayofweek == 2).all():
        raise ValueError("Expected Wednesday ENSO source dates")

    daily_means = daily_clean.rolling(7, min_periods=7).mean().reindex(weeks)
    source_dates = weeks + pd.Timedelta(days=1)
    ssta = enso_clean["nino34_ssta"]

    gold = daily_means.rename_axis("week_date").reset_index()
    for column, window in [("enso", 1), ("enso14", 2), ("enso28", 4), ("enso84", 12)]:
        gold[column] = (
            ssta.rolling(window, min_periods=window).mean().reindex(source_dates).to_numpy()
        )

    if gold.isna().any().any():
        bad = gold.loc[gold.isna().any(axis=1), "week_date"].dt.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"Missing data or incomplete averaging windows for USDM weeks: {bad[:10]}")

    gold["week_date"] = pd.to_datetime(gold["week_date"]).astype("datetime64[ns]")
    gold = gold.round(
        {
            "ao": 2,
            "nao": 2,
            "pna": 2,
            "enso": 2,
            "enso14": 3,
            "enso28": 3,
            "enso84": 3,
        }
    )
    return gold


def build_weekly_lineage(weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """Create explicit per-week traceability mapping USDM Tuesday <-> source windows."""
    rows = []
    for w in weeks:
        wed = w + pd.Timedelta(days=1)
        rows.append(
            {
                "time_id": w.strftime("%Y%m%d"),
                "week_date": w.strftime("%Y-%m-%d"),
                "daily_window_start": (w - pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
                "daily_window_end": w.strftime("%Y-%m-%d"),
                "enso_source_week_date": wed.strftime("%Y-%m-%d"),
                "enso14_window_start": (wed - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
                "enso28_window_start": (wed - pd.Timedelta(days=21)).strftime("%Y-%m-%d"),
                "enso84_window_start": (wed - pd.Timedelta(days=77)).strftime("%Y-%m-%d"),
            }
        )
    return pd.DataFrame(rows)


def write_validation_report(gold: pd.DataFrame, out_path: Path, calendar_source: str) -> None:
    """Write data_lake/gold/noaa/validation.txt mirroring USDM Gold validation report style."""
    weeks = gold["week_date"]
    value_cols = ["ao", "nao", "pna", "enso", "enso14", "enso28", "enso84"]
    stats = gold[value_cols].describe().loc[["count", "mean", "std", "min", "50%", "max"]].round(4)

    lines = [
        f"Weeks: {len(gold)}; range: {weeks.min().strftime('%Y-%m-%d')} - {weeks.max().strftime('%Y-%m-%d')}",
        f"Columns ({len(gold.columns)}): {', '.join(gold.columns)}",
        f"USDM calendar source: {calendar_source}",
        f"All Tuesdays: {bool((weeks.dt.dayofweek == 1).all())}; Duplicate weeks: {int(weeks.duplicated().sum())}; Null cells: {int(gold.isna().sum().sum())}",
        "Aggregation rules: AO/NAO/PNA = 7-day rolling mean ending on USDM Tuesday (inclusive); ENSO = Nino 3.4 SSTA (1991-2020 base) dated next Wednesday (Tuesday + 1d); enso14/28/84 = trailing 2/4/12-week SSTA means.",
        "Retrospective alignment note: matches TeleconnectionsForDryad.R (Erhardt et al., 2024); Silver inputs remain unchanged.",
        "",
        "Summary Statistics:",
        stats.to_string(),
        "",
    ]
    write_text_atomic(out_path, "\n".join(lines))


def write_input_manifest(
    manifest_path: Path,
    daily_path: Path,
    enso_path: Path,
    calendar_path: Path,
) -> None:
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_write(manifest_path) as temporary:
        with temporary.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["role", "filename", "relative_path", "size_bytes", "sha256"]
            )
            writer.writeheader()
            for role, p in [
                ("silver_daily", daily_path),
                ("silver_enso", enso_path),
                ("usdm_calendar", calendar_path),
            ]:
                try:
                    rel = str(Path(p).resolve().relative_to(paths.SERVER_ROOT.resolve()))
                except ValueError:
                    rel = str(p)
                writer.writerow(
                    {
                        "role": role,
                        "filename": Path(p).name,
                        "relative_path": rel,
                        "size_bytes": Path(p).stat().st_size,
                        "sha256": file_hash(p),
                    }
                )


def write_environment_info(env_path: Path) -> None:
    info = [
        f"Generated UTC : {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        f"Python        : {sys.version.splitlines()[0]}",
        f"Platform      : {platform.platform()}",
        f"pandas        : {pd.__version__}",
        f"numpy         : {np.__version__}",
        f"pyarrow       : {pa.__version__}",
        "",
    ]
    write_text_atomic(env_path, "\n".join(info))


def build_outputs(
    silver_root,
    gold_root,
    week_dates_csv,
    usdm_csv=None,
    overwrite: bool = False,
) -> dict:
    """Build every Gold artifact from Silver; callable by the CLI and the medallion runner."""
    silver_root = Path(silver_root)
    gold_root = Path(gold_root)
    week_dates_csv = Path(week_dates_csv)
    usdm_csv = Path(usdm_csv) if usdm_csv is not None else None

    parquet_out = gold_root / "climate_weekly.parquet"
    csv_out = gold_root / "climate_weekly.csv"
    marker = gold_root / spec.COMPLETE_MARKER

    if not overwrite and outputs_complete(gold_root, spec.COMPLETE_MARKER, spec.GOLD_OUTPUTS):
        logger.info("Gold outputs already complete. Skipping (use --overwrite to rebuild).")
        return {
            "status": "SKIPPED_EXISTING",
            "weeks": 0,
            "outputs": [str(parquet_out), str(csv_out)],
        }

    if not outputs_complete(silver_root, spec.COMPLETE_MARKER, spec.SILVER_OUTPUTS):
        raise ValueError("Silver inputs are missing or incomplete; refusing to build Gold")

    # Confirmed the inputs are whole and the rebuild is starting: drop the old marker so an
    # interrupted run looks incomplete to the next run instead of reusing stale Gold.
    marker.unlink(missing_ok=True)

    from_usdm = usdm_csv is not None and usdm_csv.exists()
    if from_usdm:
        weeks = read_usdm_weeks(usdm_csv)
        calendar_source = f"usdmfinal.csv ({usdm_csv.name})"
        calendar_file_used = usdm_csv
    else:
        weeks = read_week_dates(week_dates_csv)
        calendar_source = week_dates_csv.name
        calendar_file_used = week_dates_csv

    daily_path = silver_root / "climate_daily.parquet"
    enso_path = silver_root / "enso_weekly.parquet"
    daily = pd.read_parquet(daily_path)
    enso = pd.read_parquet(enso_path)

    gold = build_gold(daily, enso, weeks)

    gold_root.mkdir(parents=True, exist_ok=True)
    comparison_dir = gold_root / "comparison_reports"
    comparison_dir.mkdir(parents=True, exist_ok=True)

    with atomic_write(parquet_out) as temporary:
        gold.to_parquet(temporary, engine="pyarrow", compression="snappy", index=False)
    with atomic_write(csv_out) as temporary:
        gold.to_csv(temporary, index=False, date_format="%Y-%m-%d")

    if from_usdm:
        week_dates_csv.parent.mkdir(parents=True, exist_ok=True)
        with atomic_write(week_dates_csv) as temporary:
            gold[["week_date"]].to_csv(temporary, index=False, date_format="%Y-%m-%d")

    lineage_df = build_weekly_lineage(weeks)
    with atomic_write(comparison_dir / "weekly_lineage.csv") as temporary:
        lineage_df.to_csv(temporary, index=False)

    write_validation_report(gold, gold_root / "validation.txt", calendar_source)

    write_input_manifest(
        gold_root / "input_manifest.csv", daily_path, enso_path, calendar_file_used
    )
    write_environment_info(gold_root / "environment_info.txt")

    # Completion marker last: only now is the Gold layer truly done.
    write_completion_marker(
        gold_root, spec.COMPLETE_MARKER, {parquet_out.name: parquet_out, csv_out.name: csv_out}
    )

    logger.info(
        f"Wrote {parquet_out}: {len(gold)} weeks ({weeks.min().date()} .. {weeks.max().date()})"
    )
    logger.info(f"Wrote {csv_out}")
    logger.info(f"Wrote {gold_root / 'validation.txt'}")
    logger.info(f"Wrote {comparison_dir / 'weekly_lineage.csv'}")
    return {
        "status": "SUCCESS",
        "weeks": int(len(gold)),
        "start": str(weeks.min().date()),
        "end": str(weeks.max().date()),
        "from_usdm": bool(from_usdm),
        "outputs": [str(parquet_out), str(csv_out)],
    }
