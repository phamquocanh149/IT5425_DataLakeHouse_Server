"""Unit tests for the NLDAS S3 publisher (no real S3, no science stack)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from climate_platform.datasets.nldas import publish


@dataclass
class Record:
    source: str
    status: str
    is_current: bool
    s3_object_key: str
    s3_bucket: str
    original_filename: str
    sha256: str
    size_bytes: int


class FakeBronzeStore:
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


def _record(payload: bytes, filename="nldas_fora0125_h.a20210615.0000.020_processed.nc"):
    return Record(
        source="nldas",
        status="VERIFIED",
        is_current=True,
        s3_object_key="source=nldas/year=2021/date=2021-06-15/dataset=x/revision=1/sha256=y/raw.nc",
        s3_bucket="climate-bronze",
        original_filename=filename,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def test_record_path_parses_product_and_month(tmp_path):
    target = publish._record_path(tmp_path, "nldas_noah0125_h.a20210615.2300.020_processed.nc")
    assert (
        target == tmp_path / "NOAH" / "2021-06" / "nldas_noah0125_h.a20210615.2300.020_processed.nc"
    )
    assert publish._record_path(tmp_path, "not-nldas.nc") is None


def test_sync_bronze_downloads_once_then_uses_marker(tmp_path):
    payload = b"raw-hour"
    record = _record(payload)
    store = FakeBronzeStore({record.s3_object_key: payload})

    downloaded, cached = publish.sync_bronze([record], store, tmp_path)
    assert (downloaded, cached) == (1, 0)
    assert store.downloaded == [record.s3_object_key]
    target = tmp_path / "FORA" / "2021-06" / record.original_filename
    assert target.read_bytes() == payload
    assert target.with_name(target.name + ".sha256").read_text().strip() == record.sha256

    downloaded, cached = publish.sync_bronze([record], store, tmp_path)
    assert (downloaded, cached) == (0, 1)
    assert len(store.downloaded) == 1


def test_sync_bronze_repairs_corrupted_cached_file(tmp_path):
    payload = b"correct"
    record = _record(payload)
    target = tmp_path / "FORA" / "2021-06" / record.original_filename
    target.parent.mkdir(parents=True)
    target.write_bytes(b"truncated")
    store = FakeBronzeStore({record.s3_object_key: payload})

    downloaded, cached = publish.sync_bronze([record], store, tmp_path)
    assert (downloaded, cached) == (1, 0)
    assert target.read_bytes() == payload


def test_layer_artifacts_use_source_product_keys(tmp_path):
    product = tmp_path / "FORA"
    (product / "year=2021").mkdir(parents=True)
    (product / "year=2021" / "data.parquet").write_bytes(b"parquet")
    (product / "manifest_abc.json").write_text("{}", encoding="utf-8")

    artifacts = publish._layer_artifacts("silver", tmp_path, ["FORA"])

    assert [item.key for item in artifacts] == [
        "source=nldas/product=FORA/manifest_abc.json",
        "source=nldas/product=FORA/year=2021/data.parquet",
    ]


def test_sync_bronze_prunes_superseded_same_timestamp(tmp_path):
    old_payload, new_payload = b"old-hour", b"new-hour"
    old = _record(old_payload, "nldas_fora0125_h.a20210615.0000.020_processed.nc")
    new = Record(
        source="nldas",
        status="VERIFIED",
        is_current=True,
        s3_object_key="new-key",
        s3_bucket="climate-bronze",
        original_filename="nldas_fora0125_h.a20210615.0000.021_processed.nc",
        sha256=hashlib.sha256(new_payload).hexdigest(),
        size_bytes=len(new_payload),
    )
    store = FakeBronzeStore({old.s3_object_key: old_payload, new.s3_object_key: new_payload})

    publish.sync_bronze([old], store, tmp_path)
    old_target = tmp_path / "FORA" / "2021-06" / old.original_filename
    assert old_target.is_file()

    publish.sync_bronze([new], store, tmp_path)

    assert not old_target.exists()
    assert (tmp_path / "FORA" / "2021-06" / new.original_filename).read_bytes() == new_payload


def test_product_details_tolerates_missing_keys():
    from climate_platform.medallion.contracts import RunReport

    details = publish._product_details(
        RunReport(source="nldas", details={"products": {"FORA": {"ready_weeks": []}}})
    )

    assert details == {
        "FORA": {
            "bronze_hours": None,
            "ready_weeks": [],
            "built_silver": None,
            "built_gold": None,
        }
    }
