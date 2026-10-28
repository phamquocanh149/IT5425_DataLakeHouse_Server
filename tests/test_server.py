import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.main import app
from server.metadata import metadata_manager

# Test client keys
VALID_KEY_CLIENT01 = "test-only-client01"
VALID_KEY_CLIENT02 = "test-only-client02"
INVALID_KEY = "invalid_secret_key_12345"


@pytest.fixture
def client():
    """Create TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path, monkeypatch):
    """Isolate storage and metadata for each test run using tmp_path."""
    test_base = tmp_path / "lake_env"
    test_base.mkdir()
    monkeypatch.setattr(settings, "CLIENT01_API_KEY", VALID_KEY_CLIENT01)
    monkeypatch.setattr(settings, "CLIENT02_API_KEY", VALID_KEY_CLIENT02)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-only-admin")
    monkeypatch.setattr(settings, "COLLECTOR_API_KEY", "test-only-collector")
    monkeypatch.setattr(settings, "ENABLE_LEGACY_KEYS", True)

    # Monkeypatch settings properties
    monkeypatch.setattr(settings, "BASE_DIR", test_base)
    monkeypatch.setattr(settings, "DATA_LAKE_DIR", "data_lake")
    monkeypatch.setattr(settings, "METADATA_DIR", "metadata")
    monkeypatch.setattr(settings, "TEMP_DIR", "data_lake/temp")

    # Point metadata manager to temporary metadata dir
    test_metadata_dir = test_base / "metadata"
    test_metadata_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(metadata_manager, "metadata_dir", test_metadata_dir)

    settings.ensure_directories()
    yield test_base


def test_health_check(client):
    """Test 1 & 2: Health check endpoint returns 200 and expected JSON."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "climate-data-server"


def test_upload_valid_csv(client, setup_test_environment):
    """Test 3, 4, 5, 6: Upload valid CSV file, verify Bronze storage, SHA-256, and metadata."""
    csv_content = b"date,county_fips,d0,d1,d2,d3,d4\n2021-06-22,01001,15.2,5.1,0.0,0.0,0.0\n"
    expected_sha256 = hashlib.sha256(csv_content).hexdigest()

    response = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "usdm", "source_date": "2021-06-22"},
        files={"file": ("usdm_sample.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "VERIFIED"
    assert "metadata" in res_json

    meta = res_json["metadata"]
    assert meta["source"] == "usdm"
    assert meta["source_date"] == "2021-06-22"
    assert meta["client_id"] == "client01"
    assert meta["original_filename"] == "usdm_sample.csv"
    assert meta["sha256"] == expected_sha256
    assert meta["size_bytes"] == len(csv_content)
    assert meta["status"] == "VERIFIED"

    # Verify physical file existence in Bronze layer
    stored_path = setup_test_environment / meta["stored_path"]
    assert stored_path.exists()
    assert stored_path.read_bytes() == csv_content

    # Verify metadata JSON file on disk
    assert metadata_manager.db_path.exists()
    disk_metadata = metadata_manager.get_by_file_id(meta["file_id"]).model_dump()
    assert disk_metadata["sha256"] == expected_sha256
    assert disk_metadata["status"] == "VERIFIED"


def test_deduplication_on_identical_upload(client):
    """Test 7: Uploading identical file returns DUPLICATE status without creating extra files."""
    data_bytes = b"sample_noaa_precipitation_data_20210622_chunk_01"
    checksum = hashlib.sha256(data_bytes).hexdigest()

    # First upload
    res1 = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "noaa", "source_date": "2021-06-22"},
        files={"file": ("precip.txt", data_bytes, "text/plain")},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "VERIFIED"
    first_file_id = res1.json()["metadata"]["file_id"]

    # Second upload with identical bytes
    res2 = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "noaa", "source_date": "2021-06-22"},
        files={"file": ("precip.txt", data_bytes, "text/plain")},
    )
    assert res2.status_code == 200
    res2_json = res2.json()
    assert res2_json["status"] == "DUPLICATE"
    assert "already exists" in res2_json["message"]
    assert res2_json["metadata"]["file_id"] == first_file_id
    assert res2_json["metadata"]["sha256"] == checksum


def test_reject_invalid_source(client):
    """Test 8: Upload with unrecognized source is rejected with 400 Bad Request."""
    response = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "unsupported_source_xyz", "source_date": "2021-06-22"},
        files={"file": ("data.csv", b"dummy,data\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "Invalid source" in response.json()["detail"]


def test_reject_invalid_date_format(client):
    """Upload with bad source_date format is rejected."""
    response = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "usdm", "source_date": "22-06-2021"},
        files={"file": ("data.csv", b"dummy,data\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "Invalid source_date format" in response.json()["detail"]


def test_reject_file_exceeding_size_limit(client, monkeypatch):
    """Test 9: Upload exceeding max allowed file size is rejected with 413."""
    # Set limit to 1KB for fast test execution
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1024)

    large_content = b"A" * 2048  # 2KB > 1KB limit
    response = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT02},
        data={"source": "usgs", "source_date": "2021-06-22"},
        files={"file": ("streamflow.dat", large_content, "application/octet-stream")},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]


def test_authentication_enforcement(client):
    """Test 10: Missing or invalid API keys are rejected with 401 Unauthorized."""
    # 1. Missing header
    res_no_key = client.post(
        "/upload",
        data={"source": "usdm", "source_date": "2021-06-22"},
        files={"file": ("test.csv", b"content", "text/csv")},
    )
    assert res_no_key.status_code == 401

    # 2. Invalid header
    res_bad_key = client.post(
        "/upload",
        headers={"X-API-Key": INVALID_KEY},
        data={"source": "usdm", "source_date": "2021-06-22"},
        files={"file": ("test.csv", b"content", "text/csv")},
    )
    assert res_bad_key.status_code == 401

    # 3. GET /uploads without key
    assert client.get("/uploads").status_code == 401


def test_path_traversal_filename_sanitized(client, setup_test_environment):
    """Test 11: Filename with path traversal sequences cannot escape Bronze directory."""
    dangerous_filename = "../../../../../windows_system.ini"
    file_content = b"safe_climate_data_stream_line1\n"

    response = client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT02},
        data={"source": "nldas", "source_date": "2021-06-22"},
        files={"file": (dangerous_filename, file_content, "text/plain")},
    )
    assert response.status_code == 200
    meta = response.json()["metadata"]

    # Original filename should be sanitized to safe name
    assert ".." not in meta["original_filename"]
    assert "/" not in meta["original_filename"]
    assert "\\" not in meta["original_filename"]

    # Must be safely located inside bronze path
    stored_full_path = setup_test_environment / meta["stored_path"]
    assert stored_full_path.exists()
    assert (setup_test_environment / "data_lake" / "bronze" / "nldas") in stored_full_path.parents


def test_interrupted_upload_cleanup(monkeypatch, setup_test_environment):
    """Test 12: Interrupted upload cleans up temp files and creates NO verified metadata."""
    import starlette.datastructures

    async def faulty_read(self, size=-1):
        raise IOError("Simulated network drop / disk error during chunk transfer")

    monkeypatch.setattr(starlette.datastructures.UploadFile, "read", faulty_read)

    with TestClient(app, raise_server_exceptions=False) as err_client:
        res = err_client.post(
            "/upload",
            headers={"X-API-Key": VALID_KEY_CLIENT01},
            data={"source": "usdm", "source_date": "2021-06-22"},
            files={"file": ("interrupted.dat", b"half_written", "text/plain")},
        )
        assert res.status_code == 500

    # Verify no files in metadata
    meta_files = list((setup_test_environment / "metadata").glob("*.json"))
    assert len(meta_files) == 0

    # Verify temp dir is clean
    temp_files = list((setup_test_environment / "data_lake" / "temp").glob("*.tmp"))
    assert len(temp_files) == 0


def test_list_uploads_endpoint(client):
    """Verify GET /uploads lists all uploaded items and supports source filtering."""
    # Upload item for usdm
    client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "usdm", "source_date": "2021-06-22"},
        files={"file": ("usdm_file.csv", b"col1,col2\n1,2\n", "text/csv")},
    )

    # Upload item for noaa
    client.post(
        "/upload",
        headers={"X-API-Key": VALID_KEY_CLIENT01},
        data={"source": "noaa", "source_date": "2021-06-23"},
        files={"file": ("noaa_file.csv", b"col1,col2\n3,4\n", "text/csv")},
    )

    # Query all uploads
    res_all = client.get("/uploads", headers={"X-API-Key": VALID_KEY_CLIENT01})
    assert res_all.status_code == 200
    items_all = res_all.json()
    assert len(items_all) == 2

    # Query filtered by source usdm
    res_usdm = client.get("/uploads?source=usdm", headers={"X-API-Key": VALID_KEY_CLIENT01})
    assert res_usdm.status_code == 200
    items_usdm = res_usdm.json()
    assert len(items_usdm) == 1
    assert items_usdm[0]["source"] == "usdm"
