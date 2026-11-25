"""Verify the packaged NLDAS reference manifest matches the shipped bytes."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[2] / "src/climate_platform/datasets/nldas/resources"


def test_reference_manifest_matches_packaged_files():
    manifest = json.loads((RESOURCES / "reference_manifest.json").read_text(encoding="utf-8"))

    for name, expected in manifest["files"].items():
        actual = hashlib.sha256((RESOURCES / name).read_bytes()).hexdigest()
        assert actual == expected, name

    with (RESOURCES / "week_dates.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert manifest["weeks"] == len(rows)
    assert rows[0]["week_date"] == manifest["start"]
    assert rows[-1]["week_date"] == manifest["end"]
