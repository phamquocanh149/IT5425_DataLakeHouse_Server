from climate_platform.config import Settings


def test_refactor_preserves_scientific_worker_recipe_identity():
    import hashlib

    from climate_platform.datasets.usdm.processor import WORKER

    # Exact server/usdm_worker.py bytes at the pre-refactor commit 69721c8.
    assert hashlib.sha256(WORKER.read_bytes()).hexdigest() == (
        "10be63a92cf68819c79b58c93269ecd39d40f5324684ab82c9d40dd34c0b70ce"
    )


def test_legacy_storage_roots_are_preserved(tmp_path):
    config = Settings(
        _env_file=None,
        BASE_DIR=tmp_path,
        DATA_LAKE_DIR="legacy-lake",
        TEMP_DIR="legacy-temp",
    )
    assert config.bronze_path == tmp_path / "legacy-lake" / "bronze"
    assert config.silver_path == tmp_path / "legacy-lake" / "silver"
    assert config.temp_path == tmp_path / "legacy-temp"


def test_explicit_canonical_roots_win_even_when_equal_to_defaults(tmp_path):
    config = Settings(
        _env_file=None,
        BASE_DIR=tmp_path,
        DATA_LAKE_DIR="legacy-lake",
        LOCAL_DATA_DIR="data_lake",
        TEMP_DIR="legacy-temp",
        SCRATCH_DIR="data_lake/temp",
    )
    assert config.bronze_path == tmp_path / "data_lake" / "bronze"
    assert config.temp_path == tmp_path / "data_lake" / "temp"


def test_absolute_storage_roots(tmp_path):
    config = Settings(
        _env_file=None,
        BASE_DIR=tmp_path / "deployment",
        LOCAL_DATA_DIR=str(tmp_path / "lake"),
        SCRATCH_DIR=str(tmp_path / "scratch"),
        METADATA_DIR=str(tmp_path / "registry"),
    )
    assert config.bronze_path == tmp_path / "lake" / "bronze"
    assert config.temp_path == tmp_path / "scratch"
    assert config.metadata_path == tmp_path / "registry"
