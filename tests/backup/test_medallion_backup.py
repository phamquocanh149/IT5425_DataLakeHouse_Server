"""Stage 5 complete checkpoints: corruption, lineage, recipes, WAL and restore replay."""

import json
import sqlite3

import pytest

from scripts.backup.medallion_backup import create, restore, verify, reconcile, pipeline_lock
from climate_platform.config import settings
from tests.usdm.test_usdm import pipeline, run  # noqa: F401


def make(pipeline, tmp_path):
    assert run(pipeline)["succeeded"] == 1
    root = pipeline[1].parent
    bundle = tmp_path / "checkpoint"
    create(root, bundle, images=["test-image"], writers_stopped=True)
    return root, bundle


def test_restore_history_and_replay(pipeline, tmp_path, monkeypatch):
    assert run(pipeline)["succeeded"] == 1
    pipeline[2].write_bytes(b"corrected source")
    root, bundle = make(pipeline, tmp_path)
    with sqlite3.connect(root / "metadata/access.sqlite3") as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE usage (bytes INTEGER)")
        db.execute("INSERT INTO usage VALUES (123)")
        db.commit()
        second = tmp_path / "checkpoint-with-accounting"
        create(root, second, images=["test-image"], writers_stopped=True)
    target = tmp_path / "restored"
    result = restore(second, target)
    assert result["builds"] == result["observations"] == result["gold_rows"] == 2
    assert result["s3_objects_pending_live_verification"] == 0
    with sqlite3.connect(target / "metadata/access.sqlite3") as db:
        assert db.execute("SELECT bytes FROM usage").fetchone()[0] == 123
    monkeypatch.setattr(settings, "BASE_DIR", target)
    from climate_platform.datasets.usdm.processor import run_pipeline

    assert run_pipeline(pipeline[0], target / "products", "fixture-python")["skipped"] == 1
    with pytest.raises(ValueError, match="NEW"):
        restore(bundle, target)


@pytest.mark.parametrize("component", ["raw", "silver", "warehouse", "recipe", "extra"])
def test_corruption_rejected_before_target_creation(pipeline, tmp_path, component):
    _, bundle = make(pipeline, tmp_path)
    root = bundle / "payload"
    paths = {
        "raw": next((root / "data_lake/bronze").rglob("payload")),
        "silver": next((root / "products/silver").rglob("*.parquet")),
        "warehouse": root / "products/warehouse.sqlite3",
        "recipe": next((root / "recipes").glob("*.py")),
        "extra": root / "unexpected",
    }
    paths[component].write_bytes(b"corrupt")
    target = tmp_path / "restore"
    with pytest.raises(ValueError, match="checksum"):
        restore(bundle, target)
    assert not target.exists()


def test_missing_historical_recipe_fails_closed(pipeline, tmp_path):
    import shutil

    run(pipeline)
    old = next((pipeline[1] / "recipes").glob("*.py"))
    supplied = tmp_path / "historical.py"
    shutil.copyfile(old, supplied)
    old.unlink()
    with pytest.raises(FileNotFoundError):
        create(pipeline[1].parent, tmp_path / "bad", images=["test"], writers_stopped=True)
    assert not (tmp_path / "bad/manifest.json").exists()
    complete = tmp_path / "complete"
    create(pipeline[1].parent, complete, recipes=[supplied], images=["test"], writers_stopped=True)
    restored = tmp_path / "restored"
    restore(complete, restored)
    # Historical recipes survive restore -> another backup without external files.
    create(restored, tmp_path / "second", images=["test"], writers_stopped=True)


def test_warehouse_mismatch_and_pipeline_lock(pipeline, tmp_path):
    run(pipeline)
    with pipeline_lock(pipeline[1]), pytest.raises(OSError):
        create(pipeline[1].parent, tmp_path / "locked", images=["test"], writers_stopped=True)
    with sqlite3.connect(pipeline[1] / "warehouse.sqlite3") as db:
        db.execute("UPDATE gold_cells SET drought='D4'")
    with pytest.raises(ValueError, match="CSV/warehouse"):
        create(pipeline[1].parent, tmp_path / "bad", images=["test"], writers_stopped=True)


def test_lineage_mismatch(pipeline, tmp_path):
    _, bundle = make(pipeline, tmp_path)
    root = bundle / "payload"
    with sqlite3.connect(root / "products/warehouse.sqlite3") as db:
        db.execute("UPDATE builds SET revision=99")
    with pytest.raises(ValueError, match="lineage"):
        reconcile(root)


def test_acknowledgement_and_disjoint_paths(pipeline, tmp_path):
    run(pipeline)
    with pytest.raises(ValueError, match="Stop all"):
        create(pipeline[1].parent, tmp_path / "bad", images=["test"])
    with pytest.raises(ValueError, match="distinct"):
        create(pipeline[1].parent, pipeline[1] / "bad", images=["test"], writers_stopped=True)


def test_s3_requires_volume_and_live_verification(pipeline, tmp_path):
    import io

    root, bundle = make(pipeline, tmp_path)
    with sqlite3.connect(root / "metadata/ingestion.sqlite3") as db:
        raw = db.execute("SELECT stored_path FROM observations").fetchone()[0]
        db.execute(
            "UPDATE observations SET s3_bucket='test',s3_object_key='raw',s3_version_id='v1'"
        )
    with pytest.raises(ValueError, match="MinIO volume"):
        create(root, tmp_path / "incomplete", images=["test"], writers_stopped=True)
    volume = tmp_path / "minio"
    (volume / ".minio.sys").mkdir(parents=True)
    (volume / "fixture").write_bytes(b"not a real MinIO volume")
    with sqlite3.connect(root / "metadata/access.sqlite3") as db:
        db.execute("CREATE TABLE usage (id INTEGER)")
    s3_bundle = tmp_path / "s3-checkpoint"

    class FakeS3:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "test", "Key": "raw", "VersionId": "v1"}
            return {"Body": io.BytesIO((root / raw).read_bytes())}

        def list_buckets(self):
            return {"Buckets": [{"Name": "test"}]}

        def get_bucket_versioning(self, **kwargs):
            return {"Status": "Enabled"}

        def get_paginator(self, operation):
            assert operation == "list_object_versions"
            return self

        def paginate(self, **kwargs):
            return [
                {
                    "Versions": [{"Key": "raw", "VersionId": "v1", "IsLatest": True}],
                    "DeleteMarkers": [{"Key": "removed", "VersionId": "v2", "IsLatest": True}],
                }
            ]

    from scripts.backup.medallion_backup import s3_inventory

    versions = tmp_path / "versions.json"
    versions.write_text(json.dumps(s3_inventory(FakeS3())))
    create(
        root,
        s3_bundle,
        minio=volume,
        images=["test"],
        writers_stopped=True,
        version_inventory=versions,
    )
    assert verify(s3_bundle)["reconciliation"]["s3_objects_pending_live_verification"] == 1

    assert (
        reconcile(s3_bundle / "payload", s3_client=FakeS3())["s3_objects_pending_live_verification"]
        == 0
    )


def test_manifest_corruption(pipeline, tmp_path):
    _, bundle = make(pipeline, tmp_path)
    (bundle / "manifest.json").write_text(json.dumps({"format_version": 99}))
    with pytest.raises(ValueError, match="Manifest checksum"):
        verify(bundle)


def test_recovery_evidence_does_not_claim_offhost_or_service_acceptance(pipeline, tmp_path):
    import shutil
    from scripts.backup.recovery_drill import drill

    _, bundle = make(pipeline, tmp_path)
    copy = tmp_path / "second-copy"
    shutil.copytree(bundle, copy)
    evidence = drill(bundle, tmp_path / "restored", tmp_path / "report.json", verified_copy=copy)
    assert evidence["copy_bytes_verified"]
    assert evidence["data_recovery_seconds"] > 0
    assert evidence["service_rto_seconds"] is None
    assert evidence["rpo_seconds"] is None
    assert evidence["production_acceptance"] == "pending"
