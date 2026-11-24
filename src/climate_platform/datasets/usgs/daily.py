"""USGS station-daily helpers shared by the preprocess, Silver and Weekly stages.

One job: station metadata extraction and daily-calendar validation used across stages, so
no stage imports another stage. No lock, no orchestration, no publication.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd


def metadata(catalog, sites):
    records = defaultdict(list)
    for r in catalog:
        if r["site_id"] in sites and r["decision"] == "included":
            records[r["site_id"]].append(r)
    result, issues = {}, []
    for site in sorted(sites):
        rs = records[site]
        coords = []
        for r in rs:
            xy = r.get("coordinates")
            if (
                isinstance(xy, list)
                and len(xy) == 2
                and all(isinstance(v, (int, float)) and math.isfinite(v) for v in xy)
                and -180 <= xy[0] <= 180
                and -90 <= xy[1] <= 90
            ):
                coords.append(tuple(xy))
        xy = coords[0] if len(coords) == len(rs) and len(set(coords)) == 1 else None
        hucs = {}
        for level in (4, 6, 8):
            values = [r.get("huc") for r in rs]
            prefixes = [
                v[:level] for v in values if isinstance(v, str) and v.isdigit() and len(v) >= level
            ]
            hucs[level] = (
                prefixes[0] if len(prefixes) == len(rs) and len(set(prefixes)) == 1 else None
            )
        result[site] = {"coordinates": xy, "hucs": hucs}
        if not xy or not all(hucs.values()):
            issues.append({"site_id": site, "coordinates_valid": xy is not None, "hucs": hucs})
    return result, issues


def clean_day(site, day, rows):
    flags = set()
    if not rows:
        flags.add("missing_day")
    for r in rows:
        for flag in ("conflict", "invalid_numeric", "unexpected_unit"):
            if r[flag]:
                flags.add(flag)
        value = r["discharge_cfs"]
        if (value is None or not math.isfinite(value)) and not r["unexpected_unit"]:
            flags.add("invalid_numeric")
        if r["unit"] not in {"ft3/s", "ft^3/s", "ft3/s", "cfs"}:
            flags.add("unexpected_unit")
    values = {
        r["discharge_cfs"]
        for r in rows
        if r["discharge_cfs"] is not None and math.isfinite(r["discharge_cfs"])
    }
    if len(values) > 1:
        flags.add("conflict")
    return {
        "site_id": site,
        "date": day,
        "discharge_cfs": next(iter(values)) if not flags and len(values) == 1 else None,
        "qc_flags": sorted(flags),
        "source_observation_ids": sorted({r["observation_id"] for r in rows}),
        "approval_status": sorted(
            {r["approval_status"] for r in rows if r["approval_status"] is not None}
        ),
        "qualifier": sorted({r["qualifier"] for r in rows if r["qualifier"] is not None}),
    }


def validate_daily(df, site, start, end, check_qc=False):
    """One record per calendar day; missing values stay null and zero stays valid."""
    dates = pd.to_datetime(df.date, errors="raise")
    expected = pd.date_range(start, end)
    if dates.duplicated().any() or set(dates) != set(expected):
        raise ValueError(f"Incomplete or duplicate daily calendar: {site}")
    if "site_id" in df and not df.site_id.eq(site).all():
        raise ValueError(f"Unexpected station in daily table: {site}")
    values = pd.to_numeric(df.discharge_cfs, errors="raise")
    if not np.isfinite(values.dropna()).all():
        raise ValueError(f"Non-finite discharge: {site}")
    if check_qc:
        flagged = df.qc_flags.map(len).gt(0)
        if not flagged.eq(values.isna()).all() or not df.unit.eq("cfs").all():
            raise ValueError(f"Daily QC/null or unit mismatch: {site}")
