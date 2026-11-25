"""Unit tests for the shared auto-publish plumbing (no S3, no science stack)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from climate_platform.modules.processing import auto_publish


@dataclass
class Record:
    source: str = "nldas"
    status: str = "VERIFIED"
    is_current: bool = True
    s3_object_key: str = "key"
    s3_bucket: str = "climate-bronze"
    original_filename: str = "file.nc"
    sha256: str = ""
    size_bytes: int = 0
    received_at: str = ""
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


def _record(payload, *, key, received_at, revision=1):
    return Record(
        s3_object_key=key,
        original_filename="shared.nc",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        received_at=received_at,
        revision=revision,
    )


def test_download_records_writes_newest_collision_last(tmp_path):
    old_payload, new_payload = b"old", b"new"
    records = [
        _record(new_payload, key="new", received_at="2026-01-02T00:00:00+00:00", revision=2),
        _record(old_payload, key="old", received_at="2026-01-01T00:00:00+00:00", revision=1),
    ]
    store = FakeStore({"new": new_payload, "old": old_payload})
    target = tmp_path / "shared.nc"

    downloaded, cached = auto_publish.download_records(records, store, lambda record: target)

    assert (downloaded, cached) == (2, 0)
    assert target.read_bytes() == new_payload


def test_prune_cache_removes_stale_files_and_markers(tmp_path):
    keep = tmp_path / "current.nc"
    keep.write_bytes(b"current")
    keep.with_name(keep.name + ".sha256").write_text("hash\n", encoding="ascii")
    stale = tmp_path / "old.nc"
    stale.write_bytes(b"old")
    stale.with_name(stale.name + ".sha256").write_text("old\n", encoding="ascii")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "stale.txt").write_text("x", encoding="utf-8")

    removed = auto_publish.prune_cache(tmp_path, [keep])

    assert removed == 3
    assert keep.is_file()
    assert keep.with_name(keep.name + ".sha256").is_file()
    assert not stale.exists()
    assert not nested.exists()


def test_safe_record_name_rejects_path_components():
    assert auto_publish.safe_record_name("folder/name.zip") == "name.zip"
    assert auto_publish.safe_record_name("a/b/c") == "c"
    for name in ("", ".", "..", "a\\b", "a\x00b"):
        with pytest.raises(ValueError):
            auto_publish.safe_record_name(name)


@pytest.mark.parametrize(
    "member",
    [
        "..\\evil.txt",
        "\\..\\evil.txt",
        "../evil.txt",
        "/etc/passwd",
        "C:/evil",
        "C:\\evil",
        "//host/share/evil",
        "a/../../evil",
        "a\\..\\evil",
        "folder/file:stream",
    ],
)
def test_safe_archive_parts_rejects_escape_vectors(member):
    with pytest.raises(ValueError):
        auto_publish.safe_archive_parts(member)


def test_safe_archive_parts_accepts_normal_paths():
    assert auto_publish.safe_archive_parts("cache/bronze/file.txt") == (
        "cache",
        "bronze",
        "file.txt",
    )
