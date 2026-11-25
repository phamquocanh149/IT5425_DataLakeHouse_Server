"""Unit tests for the NOAA auto-publish adapter (no science stack, no real S3)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from climate_platform.datasets.noaa import publish, spec
from climate_platform.medallion.contracts import RunReport


@dataclass
class Record:
    source: str = "noaa"
    status: str = "VERIFIED"
    is_current: bool = True
    s3_object_key: str = "key"
    s3_bucket: str = "climate-bronze"
    original_filename: str = "file.csv"
    sha256: str = ""
    size_bytes: int = 0
    source_date: str = "2026-01-01"
    received_at: str = "2026-01-01T00:00:00+00:00"
    revision: int = 1
    file_id: str = "file"


class FakeStore:
    bucket = "climate-bronze"

    def __init__(self, payloads):
        self.payloads = payloads
        self.downloaded = []

    def download(self, key, destination, *, expected_size=None, expected_sha256=None):
        data = self.payloads[key]
        assert len(data) == expected_size
        assert hashlib.sha256(data).hexdigest() == expected_sha256
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        self.downloaded.append(key)
        return destination


def _records(payloads):
    return [
        Record(
            s3_object_key=name,
            original_filename=name,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
        )
        for name, data in payloads.items()
    ]


def test_sync_bronze_prunes_superseded_snapshot(tmp_path):
    old = tmp_path / "ingest_date=2025-12-31"
    old.mkdir(parents=True)
    (old / "_manifest.json").write_text("{}", encoding="utf-8")
    payloads = {name: b"payload" for name in spec.REQUIRED_BRONZE_FILES}
    payloads["_manifest.json"] = b"{}"
    store = FakeStore(payloads)

    publish.sync_bronze(_records(payloads), store, tmp_path)

    assert not old.exists()
    assert publish._latest_complete_snapshot(tmp_path) == tmp_path / "ingest_date=2026-01-01"
    for name in spec.REQUIRED_BRONZE_FILES:
        assert (tmp_path / "ingest_date=2026-01-01" / name).is_file()


def test_missing_calendar_returns_clear_reason(tmp_path, monkeypatch):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    captured = {}

    def context(**kwargs):
        captured.update(kwargs)
        return object()

    report = RunReport(
        source="noaa",
        ready=True,
        details={"calendar": "none", "calendar_ok": False},
    )
    monkeypatch.setattr(publish.pipeline, "default_context", context)
    monkeypatch.setattr(publish.pipeline, "run", lambda ctx, log: report)
    monkeypatch.setattr(publish, "_latest_complete_snapshot", lambda root: snapshot)
    calendar = tmp_path / "custom" / "week_dates.csv"
    publisher = publish.NoaaPublisher(week_dates_csv=calendar)

    artifacts, result = publisher.run([], bronze_store=FakeStore({}), cache_root=tmp_path)

    assert captured["week_dates_csv"] == calendar
    assert artifacts == []
    assert "missing NOAA week calendar" in result.reason
