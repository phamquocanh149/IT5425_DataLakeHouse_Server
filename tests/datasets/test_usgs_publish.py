"""Unit tests for the USGS auto-publish adapter (no crawl, no real S3)."""

from __future__ import annotations

import hashlib
import io
import os
import sys
import types
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from climate_platform.datasets.usgs import publish
from climate_platform.modules.processing import auto_publish


@dataclass
class Record:
    source: str = "usgs"
    status: str = "VERIFIED"
    is_current: bool = True
    s3_object_key: str = "key"
    s3_bucket: str = "climate-bronze"
    dataset_key: str = ""
    original_filename: str = "workspace.zip"
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


@pytest.mark.parametrize(
    "member",
    [
        "\\..\\evil.txt",
        "..\\evil",
        "C:/evil",
        "C:\\evil",
        "//host/share/x",
        "/etc/passwd",
        "a/../../evil",
        "folder/file:stream",
    ],
)
def test_safe_member_rejects_windows_escape_vectors(member):
    with pytest.raises(ValueError):
        publish._safe_member(member)


def test_extract_rejects_member_that_escapes_target(tmp_path):
    archive = tmp_path / "escape.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../evil.txt", b"evil")
    target = tmp_path / "bronze"

    with pytest.raises(ValueError):
        publish._extract(archive, target)
    assert not (tmp_path / "evil.txt").exists()


def test_extract_preserves_nested_relative_paths(tmp_path):
    archive = tmp_path / "workspace.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("cache/bronze/file.txt", b"payload")
    target = tmp_path / "bronze"

    publish._extract(archive, target)

    assert (target / "cache" / "bronze" / "file.txt").read_bytes() == b"payload"


def test_extract_rejects_zip_bomb(tmp_path, monkeypatch):
    archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("big.bin", b"0" * 8192)
    monkeypatch.setattr(auto_publish, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1024)

    with pytest.raises(ValueError):
        publish._extract(archive, tmp_path / "bronze")


def test_extract_rejects_member_count_limit(tmp_path, monkeypatch):
    archive = tmp_path / "many.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("a.txt", b"a")
        bundle.writestr("b.txt", b"b")
    monkeypatch.setattr(auto_publish, "MAX_ARCHIVE_MEMBERS", 1)

    with pytest.raises(ValueError):
        publish._extract(archive, tmp_path / "bronze")


def test_zip_state_prefers_newest_duplicate(tmp_path):
    old = Record(
        original_filename="workspace.zip",
        sha256="a" * 64,
        received_at="2026-01-01T00:00:00+00:00",
        revision=1,
    )
    new = Record(
        original_filename="workspace.zip",
        sha256="b" * 64,
        received_at="2026-01-02T00:00:00+00:00",
        revision=2,
    )

    assert publish._zip_state([new, old]) == {"workspace.zip": "b" * 64}


def test_non_zip_target_uses_original_filename_not_dataset_key(tmp_path):
    record = Record(dataset_key="../../outside/place", original_filename="../normal.csv")
    target = publish._target_for(tmp_path / "uploads", tmp_path / "bronze", record)

    assert target == tmp_path / "bronze" / "normal.csv"


def test_zip_target_ignores_dataset_key(tmp_path):
    record = Record(dataset_key="../../outside/place", original_filename="archive.zip")
    target = publish._target_for(tmp_path / "uploads", tmp_path / "bronze", record)

    assert target == tmp_path / "uploads" / "archive.zip"


def test_explicit_roots_win_over_environment_without_mutation(tmp_path, monkeypatch):
    from climate_platform.datasets.usgs import paths
    from climate_platform.datasets.usgs.config import Config

    monkeypatch.setenv("USGS_SILVER_ROOT", str(tmp_path / "env-silver"))
    monkeypatch.setenv("USGS_GOLD_ROOT", str(tmp_path / "env-gold"))
    before = dict(os.environ)
    cfg = Config(
        output=str(tmp_path / "bronze"),
        silver_root=str(tmp_path / "cache-silver"),
        gold_root=str(tmp_path / "cache-gold"),
    )

    silver, gold = paths.resolve_roots(cfg)

    assert silver == tmp_path / "cache-silver"
    assert gold == tmp_path / "cache-gold"
    assert dict(os.environ) == before


def _workspace_zip(payload, *, stale=True):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("checkpoint.sqlite", payload)
        if stale:
            bundle.writestr("stale.txt", b"stale")
    return buffer.getvalue()


def test_publisher_reextracts_when_zip_set_changes(tmp_path, monkeypatch):
    first, second = _workspace_zip(b"first"), _workspace_zip(b"second", stale=False)
    record = Record(
        s3_object_key="zip",
        original_filename="workspace.zip",
        sha256=hashlib.sha256(first).hexdigest(),
        size_bytes=len(first),
    )
    store = FakeStore({"zip": first})
    publisher = publish.UsgsPublisher()
    fake_pipeline = types.SimpleNamespace(
        run=lambda *args, **kwargs: pytest.fail("pipeline should not run without grid/WBD"),
        _completed_runs=lambda *args, **kwargs: [],
    )
    monkeypatch.setitem(sys.modules, "climate_platform.datasets.usgs.pipeline", fake_pipeline)

    _, result = publisher.run([record], bronze_store=store, cache_root=tmp_path)
    assert result.reason.startswith("missing USGS grid/WBD")

    new_record = Record(
        s3_object_key="zip2",
        original_filename="workspace.zip",
        sha256=hashlib.sha256(second).hexdigest(),
        size_bytes=len(second),
    )
    store.payloads["zip2"] = second
    _, result = publisher.run([new_record], bronze_store=store, cache_root=tmp_path)

    assert (tmp_path / "bronze" / "checkpoint.sqlite").read_bytes() == b"second"
    assert not (tmp_path / "bronze" / "stale.txt").exists()
    assert result.reason.startswith("missing USGS grid/WBD")
