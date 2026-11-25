"""Unit tests for the USDM auto-publish adapter (no GIS, no real S3)."""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from climate_platform.datasets.usdm import publish
from climate_platform.modules.processing import auto_publish


@dataclass
class Record:
    source: str = "usdm"
    status: str = "VERIFIED"
    is_current: bool = True
    s3_object_key: str = "key"
    s3_bucket: str = "climate-bronze"
    original_filename: str = "USDM_20210622_M.zip"
    sha256: str = ""
    size_bytes: int = 0
    source_date: str = "2021-06-22"
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


def _package(folder, grid=None):
    folder.mkdir(parents=True)
    for suffix in (".shp", ".shx", ".dbf", ".prj"):
        (folder / f"USDM_20210622{suffix}").write_bytes(b"sidecar")
    archive = folder.parent / "package.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for suffix in (".shp", ".shx", ".dbf", ".prj"):
            bundle.writestr(f"USDM_20210622_M/USDM_20210622{suffix}", b"sidecar")
        if grid is not None:
            bundle.writestr("gold/data/usdmfinal.csv", grid)
    return archive


def _record(payload, filename, key="key"):
    return Record(
        s3_object_key=key,
        original_filename=filename,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def test_weekly_record_date_ignores_reference_uploads():
    assert publish._weekly_record_date(Record(original_filename="USDM_20200107_M.zip")) == (
        "2020-01-07"
    )
    assert publish._weekly_record_date(Record(original_filename="USDM_20200107.shp")) == (
        "2020-01-07"
    )
    assert publish._weekly_record_date(Record(original_filename="usdmfinal.csv")) is None


def test_prepare_source_extracts_reference_grid_to_gold(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    grid = b"grid,lon,lat\nA,-100,35\n"
    _package(uploads / "pkg", grid=grid)
    source = tmp_path / "source"

    shapefiles, grid_path = publish._prepare_source(uploads, source)

    assert [item.name for item in shapefiles] == ["USDM_20210622.shp"]
    assert grid_path == source / "gold" / "data" / "usdmfinal.csv"
    assert grid_path.read_bytes() == grid


def test_prepare_source_uses_packaged_grid_when_upload_has_none(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _package(uploads / "pkg")
    source = tmp_path / "source"

    shapefiles, grid_path = publish._prepare_source(uploads, source)

    assert [item.name for item in shapefiles] == ["USDM_20210622.shp"]
    assert grid_path == source / "gold" / "data" / "usdmfinal.csv"
    assert grid_path.read_bytes() == publish.DEFAULT_GRID.read_bytes()


def test_prepare_source_prefers_direct_grid_record_and_replaces_stale_source(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _package(uploads / "pkg", grid=b"grid,lon,lat\nOLD,-100,35\n")
    source = tmp_path / "source"
    (source / "bronze" / "data" / "shp").mkdir(parents=True)
    stale = source / "bronze" / "data" / "shp" / "USDM_20200107.shp"
    stale.write_bytes(b"stale")
    direct = b"grid,lon,lat\nNEW,-101,36\n"
    (uploads / "usdmfinal.csv").write_bytes(direct)

    shapefiles, grid_path = publish._prepare_source(uploads, source)

    assert [item.name for item in shapefiles] == ["USDM_20210622.shp"]
    assert grid_path.read_bytes() == direct
    assert not stale.exists()


def _zip_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for suffix in (".shp", ".shx", ".dbf", ".prj"):
            bundle.writestr(f"USDM_20210622{suffix}", b"sidecar")
    return buffer.getvalue()


def test_prepare_source_accepts_equivalent_reference_csv(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    _package(uploads / "pkg")
    reference = b"time,grid,lon,lat,drought\n2020-01-07,A,-100,35,0\n"
    (uploads / "reference_grid.csv").write_bytes(reference)
    source = tmp_path / "source"

    _, grid_path = publish._prepare_source(uploads, source)

    assert grid_path.read_bytes() == reference


def test_publisher_skips_gis_without_any_grid_reference(tmp_path, monkeypatch):
    payload = _zip_bytes()
    record = _record(payload, "USDM_20210622_M.zip")
    store = FakeStore({"key": payload})
    called = []
    monkeypatch.setattr(publish, "DEFAULT_GRID", tmp_path / "absent.csv")
    monkeypatch.setattr(
        "climate_platform.datasets.usdm.pipeline.run_pipeline",
        lambda *args, **kwargs: called.append(args),
    )
    publisher = publish.UsdmPublisher(gis_python="python")

    artifacts, result = publisher.run([record], bronze_store=store, cache_root=tmp_path)

    assert artifacts == []
    assert called == []
    assert result.ready is False
    assert result.failures == {}
    assert result.reason == "missing USDM grid reference usdmfinal.csv"


def test_publisher_publishes_layer_keys_without_duplicate_source(tmp_path, monkeypatch):
    payload = _zip_bytes()
    record = _record(payload, "USDM_20210622_M.zip")
    store = FakeStore({"key": payload})

    def fake_pipeline(source, output, python, start=None, end=None, records=None):
        output = Path(output)
        silver = output / "silver/source=usdm/week_date=2021-06-22/build=abc/silver.parquet"
        gold = output / "gold/source=usdm/week_date=2021-06-22/build=abc/gold.csv"
        for path in (silver, gold):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"payload")
        return {"succeeded": 1, "skipped": 0, "failed": 0, "weeks": []}

    monkeypatch.setattr("climate_platform.datasets.usdm.pipeline.run_pipeline", fake_pipeline)
    publisher = publish.UsdmPublisher(gis_python="python")

    artifacts, result = publisher.run([record], bronze_store=store, cache_root=tmp_path)

    assert result.ready is True
    assert result.failures == {}
    assert {artifact.layer: artifact.key for artifact in artifacts} == {
        "silver": "source=usdm/week_date=2021-06-22/build=abc/silver.parquet",
        "gold": "source=usdm/week_date=2021-06-22/build=abc/gold.csv",
    }


def test_publisher_runs_pipeline_with_prepared_grid(tmp_path, monkeypatch):
    payload = _zip_bytes()
    record = _record(payload, "USDM_20210622_M.zip")
    grid_payload = b"grid,lon,lat\nA,-100,35\n"
    grid_record = _record(grid_payload, "usdmfinal.csv", key="grid")
    store = FakeStore({"key": payload, "grid": grid_payload})
    calls = []

    def fake_pipeline(source, output, python, start=None, end=None, records=None):
        calls.append((Path(source), Path(output), python, start, end, records))
        return {"succeeded": 1, "skipped": 0, "failed": 0, "weeks": []}

    monkeypatch.setattr("climate_platform.datasets.usdm.pipeline.run_pipeline", fake_pipeline)
    publisher = publish.UsdmPublisher(gis_python="python")

    artifacts, result = publisher.run(
        [record, grid_record], bronze_store=store, cache_root=tmp_path
    )

    assert result.ready is True
    assert result.failures == {}
    assert artifacts == []
    source = calls[0][0]
    assert calls[0][5] == {"2021-06-22": record}
    assert (source / "gold" / "data" / "usdmfinal.csv").read_bytes() == grid_payload
    assert (source / "bronze" / "data" / "shp" / "USDM_20210622.shp").is_file()


def test_safe_extract_rejects_zip_bomb(tmp_path, monkeypatch):
    archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("USDM_20210622.shp", b"0" * 4096)
    monkeypatch.setattr(auto_publish, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1024)

    with pytest.raises(ValueError):
        publish._safe_extract(archive, tmp_path / "out")


def test_safe_extract_rejects_member_count_limit(tmp_path, monkeypatch):
    archive = tmp_path / "many.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("a.shp", b"a")
        bundle.writestr("b.shx", b"b")
    monkeypatch.setattr(auto_publish, "MAX_ARCHIVE_MEMBERS", 1)

    with pytest.raises(ValueError):
        publish._safe_extract(archive, tmp_path / "out")
