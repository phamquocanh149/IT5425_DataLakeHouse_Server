import json
import sqlite3
from pathlib import Path

import pytest

from climate_platform.catalog.repository import file_hash
from climate_platform.config import settings
from climate_platform.datasets.usdm import processor as usdm


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    source = tmp_path / "source"
    shp = source / "bronze/data/shp/USDM_20200107_M/USDM_20200107.shp"
    shp.parent.mkdir(parents=True)
    for suffix in (".shp", ".dbf", ".shx", ".prj"):
        shp.with_suffix(suffix).write_bytes(b"original" + suffix.encode())
    cleaner = source / "silver/scripts/usdm_bronze_to_silver.py"
    cleaner.parent.mkdir(parents=True)
    cleaner.write_text("# fixture cleaner", encoding="utf-8")
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(settings, "BASE_DIR", runtime)
    monkeypatch.setattr(settings, "METADATA_DIR", "metadata")
    monkeypatch.setattr(settings, "DATA_LAKE_DIR", "data_lake")
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")

    def worker(python, args):
        args = list(map(str, args))
        if "--grid-source" in args:
            grid = Path(args[args.index("--grid") + 1])
            grid.write_text("grid,lon,lat\nA,-100,35\n", encoding="utf-8")
            grid.with_suffix(".versions.json").write_text("{}", encoding="utf-8")
        else:
            out = Path(args[args.index("--output") + 1])
            (out / "silver.parquet").write_bytes(b"fixture parquet")
            (out / "gold.csv").write_text(
                "time,grid,lon,lat,drought\n20200107,A,-100,35,D1\n", encoding="utf-8"
            )
            (out / "quality.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(usdm, "run_worker", worker)
    return source, runtime / "products", shp


def run(pipeline):
    source, output, _ = pipeline
    return usdm.run_pipeline(source, output, "fixture-python")


def counts(output):
    with sqlite3.connect(output / "warehouse.sqlite3") as db:
        return tuple(
            db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ["builds", "gold_cells"]
        )


def test_replay_and_lineage(pipeline):
    source, output, shp = pipeline
    before = {p.name: file_hash(p) for p in shp.parent.iterdir()}
    assert run(pipeline)["succeeded"] == 1
    assert run(pipeline)["skipped"] == 1
    assert counts(output) == (1, 1)
    assert before == {p.name: file_hash(p) for p in shp.parent.iterdir()}
    with sqlite3.connect(output / "warehouse.sqlite3") as db:
        manifest = json.loads(db.execute("SELECT manifest FROM builds").fetchone()[0])
    assert manifest["source_members"] == before
    assert set(manifest["products"]) == {"silver", "gold", "quality", "reference"}


def test_revision_preserves_history_and_old_replay(pipeline):
    _, output, shp = pipeline
    original = shp.read_bytes()
    run(pipeline)
    shp.write_bytes(b"correction")
    assert run(pipeline)["succeeded"] == 1
    shp.write_bytes(original)
    assert run(pipeline)["skipped"] == 1
    assert counts(output) == (2, 2)
    manager = usdm.MetadataManager()
    with manager.connection() as db:
        rows = db.execute(
            "SELECT revision,is_current FROM observations ORDER BY revision"
        ).fetchall()
    assert [tuple(r) for r in rows] == [(1, 0), (2, 1)]


def test_quality_failure_then_retry(pipeline, monkeypatch):
    original = usdm.run_worker

    def fail(python, args):
        if "--raw" in args:
            raise ValueError("Invalid DM")
        original(python, args)

    monkeypatch.setattr(usdm, "run_worker", fail)
    assert run(pipeline)["failed"] == 1
    assert counts(pipeline[1]) == (0, 0)
    monkeypatch.setattr(usdm, "run_worker", original)
    assert run(pipeline)["succeeded"] == 1
    assert counts(pipeline[1]) == (1, 1)


def test_corrupt_product_fails_closed(pipeline):
    run(pipeline)
    next(pipeline[1].glob("silver/**/*.parquet")).write_bytes(b"corrupt")
    assert run(pipeline)["failed"] == 1
    assert counts(pipeline[1]) == (1, 1)


def test_corrupt_bronze_fails_closed(pipeline):
    run(pipeline)
    next(settings.bronze_path.rglob("payload")).write_bytes(b"corrupt")
    assert run(pipeline)["failed"] == 1
    assert counts(pipeline[1]) == (1, 1)


def test_missing_sidecar(pipeline):
    pipeline[2].with_suffix(".prj").unlink()
    assert run(pipeline)["failed"] == 1
    assert counts(pipeline[1]) == (0, 0)


def test_no_input_and_source_protection(pipeline):
    source, output, _ = pipeline
    with pytest.raises(ValueError, match="disjoint"):
        usdm.run_pipeline(source, source / "out", "python")
    with pytest.raises(ValueError, match="No USDM"):
        usdm.run_pipeline(source, output, "python", start="2025-01-01")


def test_lock_released_after_error(tmp_path):
    with pytest.raises(RuntimeError):
        with usdm.exclusive_run(tmp_path):
            with pytest.raises(OSError):
                with usdm.exclusive_run(tmp_path):
                    pass
            raise RuntimeError()
    with usdm.exclusive_run(tmp_path):
        pass


def test_atomic_catalog_failure_adopts_orphans(pipeline, monkeypatch):
    original = usdm.verify_products
    calls = []

    def fail(root, manifest):
        original(root, manifest)
        calls.append(manifest)
        raise RuntimeError("simulated crash before warehouse commit")

    monkeypatch.setattr(usdm, "verify_products", fail)
    assert run(pipeline)["failed"] == 1
    assert calls and counts(pipeline[1]) == (0, 0)
    monkeypatch.setattr(usdm, "verify_products", original)
    assert run(pipeline)["succeeded"] == 1
    assert counts(pipeline[1]) == (1, 1)


def test_changed_recipe_creates_new_build(pipeline):
    run(pipeline)
    (pipeline[0] / "silver/scripts/usdm_bronze_to_silver.py").write_text(
        "# version 2", encoding="utf-8"
    )
    assert run(pipeline)["succeeded"] == 1
    assert counts(pipeline[1]) == (2, 2)


def test_warehouse_transaction_rollback(pipeline):
    output = pipeline[1]
    output.mkdir(parents=True)
    usdm.initialize_catalog(output / "warehouse.sqlite3")
    with sqlite3.connect(output / "warehouse.sqlite3") as db:
        db.execute(
            "CREATE TRIGGER reject_gold BEFORE INSERT ON gold_cells BEGIN SELECT RAISE(ABORT, 'fault'); END"
        )
    assert run(pipeline)["failed"] == 1
    assert counts(output) == (0, 0)
    with sqlite3.connect(output / "warehouse.sqlite3") as db:
        db.execute("DROP TRIGGER reject_gold")
    assert run(pipeline)["succeeded"] == 1
    assert counts(output) == (1, 1)


def test_size_limit(pipeline, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1)
    assert run(pipeline)["failed"] == 1
    with usdm.MetadataManager().connection() as db:
        assert db.execute("SELECT count(*) FROM observations").fetchone()[0] == 0
