import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from climate_platform.modules.auth.services.api_key import authenticate
from climate_platform.common.middleware import charge
from climate_platform.modules.catalog.repositories.sqlite_repository import metadata_manager
from climate_platform.config import APIKeyRecord, settings
from climate_platform.modules.system.readiness import readiness, validate_storage
from tests.api.test_server import client, setup_test_environment  # noqa: F401


def record(key_id="v1", **changes):
    values = dict(
        key_id=key_id,
        secret_hash=hashlib.sha256(b"secret").hexdigest(),
        role="collector",
        client_id="collector01",
        sources={"usdm"},
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    return APIKeyRecord(**(values | changes))


def test_missing_registry_is_unready_but_live(client):
    metadata_manager.db_path.unlink()
    readiness.reset()
    assert client.get("/livez").status_code == 200
    assert client.get("/readyz").status_code == 503
    assert client.get("/health").status_code == 503
    assert not metadata_manager.db_path.exists()


def test_writer_lock_and_recovery(client, monkeypatch):
    monkeypatch.setattr(settings, "READINESS_CACHE_SECONDS", 0)
    with sqlite3.connect(metadata_manager.db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        assert client.get("/readyz").status_code == 503
        db.rollback()
    assert client.get("/readyz").status_code == 200


def test_s3_failure_cached_and_recovery(client, monkeypatch):
    import climate_platform.modules.system.readiness as module

    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.head_bucket.side_effect = TimeoutError
    monkeypatch.setattr(module, "s3_probe_client", lambda: fake)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    readiness.reset()
    for _ in range(3):
        assert client.get("/readyz").status_code == 503
    assert fake.head_bucket.call_count == 1
    fake.head_bucket.side_effect = None
    readiness.reset()
    assert client.get("/readyz").status_code == 200


def test_startup_storage_contract(client, monkeypatch):
    import climate_platform.modules.system.readiness as module

    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.get_bucket_policy.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucketPolicy"}}, "GetBucketPolicy"
    )
    fake.get_bucket_versioning.return_value = {"Status": "Suspended"}
    monkeypatch.setattr(module, "s3_probe_client", lambda: fake)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    with pytest.raises(RuntimeError, match="versioning"):
        validate_storage()
    fake.get_bucket_versioning.return_value = {"Status": "Enabled"}
    validate_storage()
    fake.get_bucket_policy.side_effect = None
    fake.get_bucket_policy.return_value = {
        "Policy": json.dumps({"Statement": [{"Effect": "Allow", "Principal": "*"}]})
    }
    with pytest.raises(RuntimeError, match="policy"):
        validate_storage()
    fake.get_bucket_policy.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "GetBucketPolicy"
    )
    with pytest.raises(ClientError):
        validate_storage()


def test_rotation_expiry_revocation(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_STATIC_KEYS", False)
    monkeypatch.setattr(settings, "API_KEYS", [record(), record("v2")])
    assert authenticate("v1.secret") == ("collector01", "v1")
    assert authenticate("v2.secret") == ("collector01", "v2")
    settings.API_KEYS[0].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    for bad in ("v1.secret", "v2.wrong", "test-only-admin", "", "v2.秘密"):
        with pytest.raises(HTTPException) as exc:
            authenticate(bad)
        assert exc.value.status_code == 401
    settings.API_KEYS[1].enabled = False
    with pytest.raises(HTTPException):
        authenticate("v2.secret")


def test_limits_are_atomic_and_persist(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 3)

    def attempt(_):
        try:
            charge("concurrent", request=True)
            return 200
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(10)))
    assert results.count(200) == 3
    assert results.count(429) == 7
    monkeypatch.setattr(settings, "DAILY_UPLOAD_QUOTA_BYTES", 10)
    charge("quota", size=10)
    with pytest.raises(HTTPException) as exc:
        charge("quota", size=1)
    assert exc.value.status_code == 429
    charge("other", size=10)


def test_rate_quota_and_audit(client, monkeypatch, caplog):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    with caplog.at_level("INFO", logger="climate_platform.audit"):
        assert client.get("/uploads", headers={"X-API-Key": "test-only-admin"}).status_code == 200
        response = client.get("/uploads", headers={"X-API-Key": "test-only-admin"})
        assert response.status_code == 429 and "Retry-After" in response.headers
        assert client.post("/upload", content=b"bad multipart").status_code == 401
    assert '"key_id": "static-admin"' in caplog.text
    assert "test-only-admin" not in caplog.text
    monkeypatch.setattr(settings, "DAILY_UPLOAD_QUOTA_BYTES", 5)
    response = client.post(
        "/upload",
        headers={"X-API-Key": "test-only-collector"},
        data={"source": "usdm", "source_date": "2026-01-01"},
        files={"file": ("test.csv", b"0123456789")},
    )
    assert response.status_code == 429
    assert not metadata_manager.list_all()


def test_expiring_key_upload_preserves_identity(client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_STATIC_KEYS", False)
    monkeypatch.setattr(settings, "API_KEYS", [record()])
    response = client.post(
        "/upload",
        headers={"X-API-Key": "v1.secret"},
        data={"source": "usdm", "source_date": "2026-01-01"},
        files={"file": ("test.csv", b"a,b\n1,2")},
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["client_id"] == "collector01"
    assert client.get("/uploads", headers={"X-API-Key": "v1.secret"}).status_code == 200


def test_accounting_failure_is_unready_and_fails_closed(client):
    path = settings.metadata_path / "access.sqlite3"
    path.unlink()
    readiness.reset()
    assert client.get("/readyz").status_code == 503
    assert client.get("/uploads", headers={"X-API-Key": "test-only-admin"}).status_code == 503
    assert not path.exists()


def test_rotation_cannot_reset_client_limits(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    charge("old", client_id="collector", request=True)
    with pytest.raises(HTTPException) as exc:
        charge("new", client_id="collector", request=True)
    assert exc.value.status_code == 429
    charge("independent", client_id="different", request=True)


def test_optional_storage_controls(client, monkeypatch):
    import climate_platform.modules.system.readiness as module

    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.get_bucket_versioning.return_value = {"Status": "Enabled"}
    fake.get_bucket_policy.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucketPolicy"}}, "GetBucketPolicy"
    )
    fake.get_bucket_encryption.return_value = {"ServerSideEncryptionConfiguration": {"Rules": []}}
    monkeypatch.setattr(module, "s3_probe_client", lambda: fake)
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "REQUIRE_SSE_KMS", True)
    with pytest.raises(RuntimeError, match="SSE-KMS"):
        validate_storage()
    fake.get_bucket_encryption.return_value = {
        "ServerSideEncryptionConfiguration": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
        }
    }
    monkeypatch.setattr(settings, "REQUIRE_OBJECT_LOCK", True)
    fake.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}
    }
    with pytest.raises(RuntimeError, match="retention"):
        validate_storage()
    fake.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 30}},
        }
    }
    validate_storage()


def test_startup_rejects_invalid_dependencies(monkeypatch):
    from fastapi.testclient import TestClient
    import climate_platform.app as main

    def fail():
        raise RuntimeError("invalid storage configuration")

    monkeypatch.setattr(main, "validate_storage", fail)
    with pytest.raises(RuntimeError, match="invalid storage"):
        with TestClient(main.app):
            pass
