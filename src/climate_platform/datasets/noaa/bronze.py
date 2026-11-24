"""NOAA Bronze state: locate the latest snapshot and check it is complete.

One job: read-only inspection of Bronze. This layer never writes Bronze and never touches
Silver/Gold. The crawl that produces Bronze runs in the Client, not here.
"""

from __future__ import annotations

from pathlib import Path

from climate_platform.datasets.noaa import spec
from climate_platform.medallion.contracts import Readiness


def latest_snapshot(bronze_root) -> Path:
    """Newest ``ingest_date=*`` folder, or ``bronze_root`` itself when flat."""
    folders = sorted(Path(bronze_root).glob("ingest_date=*"))
    return folders[-1] if folders else Path(bronze_root)


def inspect(snapshot_dir) -> Readiness:
    """A snapshot is eligible once its crawl manifest and every kept file exist."""
    snapshot = Path(snapshot_dir)
    if not (snapshot / "_manifest.json").is_file():
        return Readiness(False, "missing _manifest.json (crawl not finished for this partition)")
    missing = [name for name in spec.REQUIRED_BRONZE_FILES if not (snapshot / name).is_file()]
    if missing:
        return Readiness(False, f"missing Bronze files: {', '.join(missing)}")
    return Readiness(True, "", {"snapshot": str(snapshot)})


def is_snapshot_complete(snapshot_dir) -> bool:
    return inspect(snapshot_dir).ready
