#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOAA CPC Teleconnections Bronze Crawler
=======================================
Downloads the 4 official NOAA Climate Prediction Center (CPC) teleconnection
datasets into an immutable, date-partitioned Bronze snapshot:

    data_lake/bronze/noaa/ingest_date=YYYY-MM-DD/
        - norm.daily.ao.cdas.z1000.19500101_current.csv   (AO daily index)
        - norm.daily.nao.cdas.z500.19500101_current.csv   (NAO daily index)
        - norm.daily.pna.cdas.z500.19500101_current.csv   (PNA daily index)
        - wksst9120.for                                   (Weekly Nino 3.4 SST/SSTA, 1991-2020 base)
        - _manifest.json                                  (Source + saved SHA-256, URLs, row counts)

Also updates data_lake/bronze/noaa/manifest_download.csv with ingestion status records.

Usage:
    python bronze/scripts/crawl_noaa_cpc.py
    python bronze/scripts/crawl_noaa_cpc.py --start-date 2019-01-01 --end-date 2022-12-31
    python bronze/scripts/crawl_noaa_cpc.py --keep-raw-full --overwrite
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CPC_DAILY_BASE = "https://ftp.cpc.ncep.noaa.gov/cwlinks/"
DAILY_FILES: Dict[str, str] = {
    "ao": "norm.daily.ao.cdas.z1000.19500101_current.csv",
    "nao": "norm.daily.nao.cdas.z500.19500101_current.csv",
    "pna": "norm.daily.pna.cdas.z500.19500101_current.csv",
}
ENSO_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
ENSO_OUT = "wksst9120.for"

SERVER_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BRONZE_ROOT = (
    Path(os.environ["NOAA_BRONZE_ROOT"])
    if os.environ.get("NOAA_BRONZE_ROOT")
    else SERVER_ROOT / "data_lake" / "bronze" / "noaa"
)


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def filter_daily(raw: bytes, start: date, end: date) -> Tuple[str, int]:
    """Keep CSV header and raw daily lines within [start, end] verbatim."""
    lines = raw.decode("utf-8").splitlines()
    keep = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            continue
        y, m, d = (int(x) for x in line.split(",")[:3])
        if start <= date(y, m, d) <= end:
            keep.append(line)
    return "\n".join(keep) + "\n", len(keep) - 1


def filter_enso(raw: bytes, start: date, end: date) -> Tuple[str, int]:
    """Slice fixed-width .for lines to Week (0:12) + Nino3.4 SST/SSTA (36:49) within [start, end]."""
    lines = raw.decode("utf-8").splitlines()
    assert lines[3].lstrip().startswith("Week"), (
        "Row 4 is not the expected 'Week' header in wksst9120.for"
    )
    header = [
        lines[0],
        lines[1],
        " " * 12 + "   Nino34",
        " Week".ljust(12) + "      SST SSTA",
    ]
    kept: List[str] = []
    for line in lines[4:]:
        if not line.strip():
            continue
        week = datetime.strptime(line[:12].strip(), "%d%b%Y").date()
        if start <= week <= end:
            kept.append(line[:12] + line[36:49])
    return "\n".join(header + kept) + "\n", len(kept)


def update_manifest_csv(csv_path: Path, records: List[Dict[str, object]]) -> None:
    """Append or write ingestion rows to data_lake/bronze/noaa/manifest_download.csv."""
    fieldnames = [
        "ingest_date",
        "category",
        "filename",
        "url",
        "status",
        "source_size_bytes",
        "saved_size_bytes",
        "rows_kept",
        "kept_range",
        "saved_sha256",
        "error",
    ]
    existing_rows: List[Dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            existing_rows = list(csv.DictReader(f))

    ingest_dates_new = {str(r["ingest_date"]) for r in records}
    kept_existing = [r for r in existing_rows if r.get("ingest_date") not in ingest_dates_new]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in kept_existing:
            writer.writerow(row)
        for rec in records:
            writer.writerow(rec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl NOAA/CPC teleconnection indices (AO, NAO, PNA, ENSO Nino3.4) into Bronze."
    )
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=DEFAULT_BRONZE_ROOT,
        help="Destination Bronze data directory (default: data_lake/bronze/noaa).",
    )
    parser.add_argument(
        "--ingest-date",
        type=str,
        default=date.today().isoformat(),
        help="Partition ingest date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2019-01-01",
        help="Start date for buffered Bronze retention (default: 2019-01-01).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2022-12-31",
        help="End date for buffered Bronze retention (default: 2022-12-31).",
    )
    parser.add_argument(
        "--keep-raw-full",
        action="store_true",
        help="Save complete untouched NOAA upstream files without date/column slicing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing snapshot if ingest_date partition already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    folder = args.bronze_root / f"ingest_date={args.ingest_date}"

    if (folder / "_manifest.json").exists() and not args.overwrite:
        print(
            f"[SKIP] {folder} already contains _manifest.json. "
            "Use --overwrite to re-crawl this partition."
        )
        return

    folder.mkdir(parents=True, exist_ok=True)

    daily_fields = "year, month, day, giá trị chỉ số"
    enso_fields = (
        "week, nino34_sst, nino34_ssta (Nino 3.4; mốc khí hậu 1991-2020); "
        "định dạng .for, cột cố định [12, 9, 4]"
        if not args.keep_raw_full
        else "raw full wksst9120.for (Nino1+2, Nino3, Nino34, Nino4; mốc khí hậu 1991-2020)"
    )

    jobs = [
        (idx, CPC_DAILY_BASE + fname, fname, "daily", daily_fields)
        for idx, fname in DAILY_FILES.items()
    ]
    jobs.append(("enso", ENSO_URL, ENSO_OUT, "enso", enso_fields))

    manifest: List[Dict[str, object]] = []
    csv_records: List[Dict[str, object]] = []

    for category, url, out_name, kind, fields in jobs:
        print(f"Downloading {url} ...")
        raw = fetch(url)
        if args.keep_raw_full:
            saved_bytes = raw
            rows = max(
                0,
                len(raw.decode("utf-8", errors="replace").splitlines())
                - (1 if kind == "daily" else 4),
            )
            kept_range = "full_history"
        else:
            if kind == "daily":
                text, rows = filter_daily(raw, start, end)
            else:
                text, rows = filter_enso(raw, start, end)
            saved_bytes = text.encode("utf-8")
            kept_range = f"{start} .. {end}"

        out_path = folder / out_name
        out_path.write_bytes(saved_bytes)
        saved_sha = hashlib.sha256(saved_bytes).hexdigest()

        manifest.append(
            {
                "file": out_name,
                "source_url": url,
                "ingest_date": args.ingest_date,
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "source_size_bytes": len(raw),
                "saved_sha256": saved_sha,
                "kept_range": kept_range,
                "rows_kept": rows,
                "kept_fields": fields,
            }
        )
        csv_records.append(
            {
                "ingest_date": args.ingest_date,
                "category": category,
                "filename": out_name,
                "url": url,
                "status": "DOWNLOADED",
                "source_size_bytes": len(raw),
                "saved_size_bytes": len(saved_bytes),
                "rows_kept": rows,
                "kept_range": kept_range,
                "saved_sha256": saved_sha,
                "error": "",
            }
        )

    (folder / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    update_manifest_csv(args.bronze_root / "manifest_download.csv", csv_records)
    print(f"Done: {folder} ({len(manifest)} files recorded).")


if __name__ == "__main__":
    main()
