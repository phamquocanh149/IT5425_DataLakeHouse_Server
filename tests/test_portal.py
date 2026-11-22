"""Portal policy and immutable selection tests; isolated from workstation data/keys."""

import json
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.portal.app import install_portal
from server.portal.config import PortalConfig
from server.portal.releases import dataset_id, sha256, verify_release, activate
from server.portal.store import token_hash


def test_reader_timeout_and_size_budget(portal, monkeypatch):
    import subprocess
    from server.portal import reader
    from server.portal.store import PortalError

    large = portal["root"] / "large.json"
    large.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(PortalError) as error:
        reader.bounded_read({"operation": "table", "path": str(large)})
    assert error.value.status == 413

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("reader", 5)

    monkeypatch.setattr(reader.subprocess, "run", timeout)
    with pytest.raises(PortalError) as error:
        reader.bounded_read({"operation": "table", "path": str(large)})
    assert error.value.code == "READ_TIMEOUT"


def test_independent_restore_invalidates_sessions(portal):
    from scripts.portal_backup import copy_portal
    from server.portal.store import Store

    login(portal)
    destination = portal["root"].parent / (portal["root"].name + "-restore")
    import shutil

    try:
        assert copy_portal(portal["root"], destination) == "fixture-v1"
        restored = Store(destination)
        with restored.db() as db:
            assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM grants").fetchone()[0] == 3
            assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        verify_release(destination, "fixture-v1")
        with pytest.raises(ValueError):
            copy_portal(portal["root"], destination)
    finally:
        if destination.exists():
            shutil.rmtree(destination)


@pytest.mark.parametrize("fault", [None, "nonce", "iss", "aud", "exp", "signature", "malformed"])
def test_oidc_signed_token_validation(portal, monkeypatch, fault):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from server.portal import auth

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())) | {"kid": "test"}
    flow = portal["store"].transient(
        "oauth", "", {"verifier": "verifier", "nonce": "expected", "return_to": "/portal/"}, 300
    )
    claims = {
        "iss": portal["cfg"].oidc_issuer,
        "aud": portal["cfg"].oidc_client_id,
        "sub": "signed-user",
        "nonce": "expected",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    if fault in {"nonce", "iss", "aud"}:
        claims[fault] = "wrong"
    if fault == "exp":
        claims["exp"] = int(time.time()) - 60
    signing_key = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        if fault == "signature"
        else key
    )
    encoded = (
        "broken"
        if fault == "malformed"
        else jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test"})
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    class HTTP:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, data):
            assert data["code_verifier"] == "verifier"
            return Result({"id_token": encoded})

        def get(self, url):
            return Result({"keys": [jwk]})

    monkeypatch.setattr(
        auth,
        "oidc_document",
        lambda cfg: {"token_endpoint": "https://idp/token", "jwks_uri": "https://idp/keys"},
    )
    monkeypatch.setattr(auth.httpx, "Client", HTTP)
    client = portal["client"]
    client.cookies.set("portal_login", flow)
    result = client.get(
        "/api/portal/v1/auth/callback",
        params={"code": "code", "state": flow},
        follow_redirects=False,
    )
    assert result.status_code == (401 if fault else 303)
    if fault:
        assert "portal_session" not in result.cookies
    else:
        assert client.get("/api/portal/v1/session").json()["role"] == "Viewer"
        assert client.get("/api/portal/v1/overview").json()["dataset_count"] == 0


def test_oidc_rejects_state_and_missing_admin_user(portal):
    client = portal["client"]
    assert client.get("/api/portal/v1/auth/callback?code=x&state=wrong").status_code == 401
    login(portal, role="Admin")
    assert (
        client.patch(
            "/api/portal/v1/admin/users/missing",
            json={"role": "Viewer", "enabled": True},
            headers={"If-None-Match": "*"},
        ).status_code
        == 404
    )


def fixture_release(root, rid="fixture-v1"):
    path = root / "releases" / rid
    path.mkdir(parents=True)
    did = dataset_id("usdm", "usdm/gis/CONUS/M/weekly")
    catalog = {
        "datasets": {
            did: {
                "dataset_id": did,
                "source": "usdm",
                "dataset_key": "usdm/gis/CONUS/M/weekly",
                "display_name": "USDM CONUS",
                "layers": ["bronze", "silver", "gold"],
            }
        },
        "observations": [],
        "builds": {},
    }
    for fid, week, current, revision in [
        ("old", "2020-01-07", False, 1),
        ("new", "2020-01-07", True, 2),
        ("week2", "2020-01-14", True, 1),
    ]:
        raw = path / "data_lake/bronze" / fid / "payload"
        raw.parent.mkdir(parents=True)
        raw.write_bytes(b"raw snapshot " + fid.encode())
        catalog["observations"].append(
            {
                "file_id": fid,
                "dataset_id": did,
                "source_date": week,
                "is_current": current,
                "revision": revision,
                "status": "VERIFIED",
                "received_at": "2026-11-21T00:00:00Z",
                "stored_path": raw.relative_to(path).as_posix(),
                "sha256": sha256(raw),
                "size_bytes": raw.stat().st_size,
                "members": [
                    {"name": "source.shp", "extension": ".shp", "size_bytes": 5, "sha256": "a" * 64}
                ],
            }
        )
    (path / "products").mkdir()
    with closing(sqlite3.connect(path / "products/warehouse.sqlite3")) as db, db:
        db.executescript(
            "CREATE TABLE gold_cells(build_id TEXT,time TEXT,grid TEXT,lon REAL,lat REAL,drought TEXT); CREATE TABLE attempts(attempt_id INTEGER,source_date TEXT,status TEXT,created_at TEXT,detail TEXT);"
        )
        db.execute(
            "INSERT INTO attempts VALUES (1,'2020-01-14','failed','2026-11-22T00:00:00Z','SECRET path credentials')"
        )
        for bid, fid, completed in [
            ("older", "old", "2026-11-20T00:00:00Z"),
            ("pilot", "week2", "2026-11-20T00:00:00Z"),
            ("latest", "week2", "2026-11-21T00:00:00Z"),
        ]:
            folder = path / "serving" / bid
            folder.mkdir(parents=True)
            table = {
                "columns": [{"name": "dm_value", "type": "int8", "nullable": False}],
                "rows": [{"dm_value": 1}, {"dm_value": 4}],
            }
            (folder / "table.json").write_text(json.dumps(table))
            for level in range(3):
                (folder / f"map-{level}.json").write_text(
                    json.dumps(
                        {
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "id": 0,
                                    "bbox": [-101, 34, -99, 36],
                                    "geometry": {
                                        "type": "Polygon",
                                        "coordinates": [
                                            [[-101, 34], [-99, 34], [-99, 36], [-101, 34]]
                                        ],
                                    },
                                    "properties": {"drought": "D1"},
                                }
                            ],
                            "metadata": {"geometry_simplified": True, "tolerance_degrees": 0.01},
                        }
                    )
                )
            products = {}
            for layer, content in [
                ("silver", b"immutable parquet bytes"),
                (
                    "gold",
                    b"time,grid,lon,lat,drought\n20200114,A,-100,35,D1\n20200114,B,-110,40,0\n",
                ),
                ("quality", b"{}"),
            ]:
                file = path / "products" / (bid + "-" + layer)
                file.write_bytes(content)
                products[layer] = {
                    "path": file.relative_to(path).as_posix(),
                    "sha256": sha256(file),
                    "size_bytes": len(content),
                }
            catalog["builds"][bid] = {
                "build_id": bid,
                "file_id": fid,
                "completed_at": completed,
                "products": products,
                "recipe": {"grid": "private-reference-hash", "libraries": {"pandas": "test"}},
                "counts": {"silver": 2, "gold": 2},
                "quality": {
                    "silver": {"repaired_geometries_count": 1},
                    "gold": {"gold_cells": 2, "counts": {"0": 1, "D1": 1}},
                },
            }
            db.executemany(
                "INSERT INTO gold_cells VALUES (?,?,?,?,?,?)",
                [
                    (bid, "20200114", "A", -100.0, 35.0, "D1"),
                    (bid, "20200114", "B", -110.0, 40.0, "0"),
                ],
            )
    (path / "catalog.json").write_text(json.dumps(catalog))
    info = {
        "release_id": rid,
        "status": "complete",
        "as_of": "2026-11-21T00:00:00Z",
        "hashes": {
            p.relative_to(path).as_posix(): sha256(p) for p in path.rglob("*") if p.is_file()
        },
    }
    (path / "release.json").write_text(json.dumps(info))
    return did, path


@pytest.fixture
def portal():
    with tempfile.TemporaryDirectory(prefix="climate-portal-tests-") as temp:
        root = Path(temp)
        did, path = fixture_release(root)
        cfg = PortalConfig(
            enabled=True,
            demo=True,
            origin="http://127.0.0.1:8010",
            oidc_issuer="http://127.0.0.1:8010/demo-idp",
            storage_root=root,
        )
        app = FastAPI()
        store = install_portal(app, cfg)
        activate(root, "fixture-v1")
        with TestClient(app, base_url=cfg.origin) as client:
            yield {
                "root": root,
                "path": path,
                "did": did,
                "cfg": cfg,
                "app": app,
                "store": store,
                "client": client,
            }


def login(p, subject="viewer", layers=("bronze", "silver", "gold"), download=True, role="Viewer"):
    token, user = p["store"].user_login(p["cfg"].oidc_issuer, subject, subject, "")
    with p["store"].db() as db:
        db.execute("UPDATE users SET role=? WHERE user_id=?", (role, user["user_id"]))
        for layer in layers:
            db.execute(
                "INSERT OR REPLACE INTO grants VALUES (?,?,?,?,1)",
                (
                    user["user_id"],
                    p["did"],
                    layer,
                    json.dumps(["read", "download"] if download else ["read"]),
                ),
            )
    p["client"].cookies.set("portal_session", token)
    s = p["client"].get("/api/portal/v1/session").json()
    p["client"].headers.update({"Origin": p["cfg"].origin, "X-CSRF-Token": s["csrf_token"]})
    return user, token


def selection(p, week="2020-01-14", **kwargs):
    return p["client"].post(
        "/api/portal/v1/selections",
        json={"dataset_id": p["did"], "week": week, "release_id": "fixture-v1", **kwargs},
    )


def test_no_session_and_no_grant(portal):
    c = portal["client"]
    assert c.get("/api/portal/v1/overview").status_code == 401
    login(portal, layers=())
    assert c.get("/api/portal/v1/overview").json()["dataset_count"] == 0
    assert c.get("/api/portal/v1/datasets/" + portal["did"]).status_code == 404


def test_current_counts_exclude_pilot_and_old_revision(portal):
    login(portal)
    result = portal["client"].get("/api/portal/v1/overview").json()
    assert result["week_count"] == 2
    assert result["gold_rows"] == 2
    s = selection(portal).json()
    assert s["build_id"] == "latest"
    assert s["layers"]["gold"]["availability"] == "available"
    missing = selection(portal, week="2020-01-07").json()
    assert missing["file_id"] == "new"
    assert missing["build_id"] is None
    assert missing["layers"]["gold"]["availability"] == "not_built"


def test_quality_and_lineage_hide_other_layers(portal):
    login(portal, layers=("gold",), download=False)
    c = portal["client"]
    overview = c.get("/api/portal/v1/overview").json()
    assert overview["repairs"] is None and overview["silver_features"] is None
    assert set(overview["layers"]) == {"gold"}
    s = selection(portal).json()
    base = f"/api/portal/v1/selections/{s['selection_id']}/layers/"
    assert s["file_id"] is None and set(s["layers"]) == {"gold"}
    assert c.get(base + "silver/preview").status_code == 404
    line = c.get(base + "gold/lineage").json()
    assert line["nodes"][0]["restricted"] and "id" not in line["nodes"][0]
    assert "repaired_geometries_count" not in c.get(base + "gold/quality").text
    aid = s["layers"]["gold"]["artifacts"][0]["artifact_id"]
    assert (
        c.get(f"/api/portal/v1/selections/{s['selection_id']}/artifacts/{aid}/download").status_code
        == 403
    )


def test_admin_not_data_superuser(portal):
    login(portal, subject="admin", role="Admin", layers=())
    assert portal["client"].get("/api/portal/v1/datasets").json()["items"] == []
    assert len(portal["client"].get("/api/portal/v1/admin/datasets").json()["items"]) == 1


def test_selection_user_binding_and_expiry(portal):
    login(portal)
    s = selection(portal).json()
    url = f"/api/portal/v1/selections/{s['selection_id']}/layers/gold/preview"
    login(portal, subject="other")
    assert portal["client"].get(url).status_code == 404
    login(portal)
    with portal["store"].db() as db:
        db.execute("UPDATE transient SET expires=0 WHERE kind='selection'")
    assert portal["client"].get(url).status_code == 410


def test_sessions_expire_and_disabled_user(portal):
    user, token = login(portal)
    with portal["store"].db() as db:
        db.execute("UPDATE sessions SET last_used=0 WHERE token=?", (token_hash(token),))
    assert portal["client"].get("/api/portal/v1/session").status_code == 401
    login(portal)
    with portal["store"].db() as db:
        db.execute("UPDATE users SET enabled=0 WHERE user_id=?", (user["user_id"],))
    assert portal["client"].get("/api/portal/v1/session").status_code == 401


def test_csrf_origin_and_input_validation(portal):
    login(portal)
    portal["client"].headers["Origin"] = "https://attacker.invalid"
    assert selection(portal).status_code == 403
    portal["client"].headers["Origin"] = portal["cfg"].origin
    assert selection(portal, unknown="field").status_code == 422
    assert selection(portal, mode="history").status_code == 422


def test_pagination_and_cursor_scope(portal):
    login(portal)
    c = portal["client"]
    url = f"/api/portal/v1/datasets/{portal['did']}/weeks?limit=1"
    first = c.get(url).json()
    second = c.get(url + "&cursor=" + first["page"]["next_cursor"]).json()
    assert first["items"][0]["week"] != second["items"][0]["week"]
    assert second["page"]["next_cursor"] is None
    assert c.get(url + "&from=2020-01-01&cursor=" + first["page"]["next_cursor"]).status_code == 400
    assert c.get(url + "&cursor=forged").status_code in {400, 404}
    assert c.get(url.replace("limit=1", "limit=10000")).status_code == 422


def test_history_does_not_change_current(portal):
    login(portal)
    c = portal["client"]
    versions = c.get(f"/api/portal/v1/datasets/{portal['did']}/weeks/2020-01-14/versions").json()[
        "items"
    ]
    pilot = next(v for v in versions if v["build_id"] == "pilot")
    s = selection(portal, mode="history", version_id=pilot["version_id"]).json()
    assert s["build_id"] == "pilot" and s["mode"] == "history"
    assert selection(portal).json()["build_id"] == "latest"
    assert (
        selection(
            portal, week="2020-01-07", mode="history", version_id=pilot["version_id"]
        ).status_code
        == 422
    )


def test_bronze_only_history_does_not_leak_builds(portal):
    login(portal, layers=("bronze",))
    result = (
        portal["client"]
        .get(f"/api/portal/v1/datasets/{portal['did']}/weeks/2020-01-14/versions")
        .json()
    )
    assert len(result["items"]) == 1 and result["items"][0]["build_id"] is None


def test_snapshot_switch_keeps_existing_selection(portal):
    login(portal)
    s = selection(portal).json()
    fixture_release(portal["root"], "fixture-v2")
    activate(portal["root"], "fixture-v2")
    assert portal["client"].get("/api/portal/v1/overview").json()["release_id"] == "fixture-v2"
    assert (
        portal["client"]
        .get(f"/api/portal/v1/selections/{s['selection_id']}/layers/gold/preview")
        .json()["release_id"]
        == "fixture-v1"
    )


def test_download_hash_range_and_cross_artifact(portal):
    login(portal)
    s = selection(portal).json()
    c = portal["client"]
    aid = s["layers"]["gold"]["artifacts"][0]["artifact_id"]
    base = f"/api/portal/v1/selections/{s['selection_id']}/artifacts/"
    r = c.get(base + aid + "/download")
    import hashlib

    assert (
        r.status_code == 200
        and hashlib.sha256(r.content).hexdigest() == r.headers["X-Content-SHA256"]
    )
    assert r.headers["Content-Disposition"].startswith("attachment;")
    assert c.get(base + aid + "/download", headers={"Range": "bytes=0-10"}).status_code == 416
    assert c.get(base + "gold_pilot/download").status_code == 404


def test_corrupt_artifact_fails_without_fallback(portal):
    login(portal)
    (portal["path"] / "products/latest-gold").write_bytes(b"corrupt")
    s = selection(portal).json()
    assert s["build_id"] == "latest" and s["layers"]["gold"]["availability"] == "unavailable"
    assert (
        portal["client"]
        .get(f"/api/portal/v1/selections/{s['selection_id']}/layers/gold/preview")
        .status_code
        == 503
    )


def test_operator_attempts_readonly_and_redacted(portal):
    login(portal)
    url = f"/api/portal/v1/datasets/{portal['did']}/attempts"
    assert portal["client"].get(url).status_code == 403
    login(portal, role="Operator")
    r = portal["client"].get(url)
    assert r.status_code == 200 and "SECRET" not in r.text and r.json()["live"] is False
    assert portal["client"].post(url + "/retry", json={}).status_code == 404


def test_map_filters_and_legend_labels(portal):
    login(portal)
    s = selection(portal).json()
    url = f"/api/portal/v1/selections/{s['selection_id']}/layers/"
    r = portal["client"].get(url + "gold/map?bbox=-105,30,-95,39&zoom=3").json()
    assert len(r["features"]) == 1 and r["features"][0]["properties"]["drought"] == "D1"
    assert portal["client"].get(url + "silver/map?drought=0").status_code == 422
    assert portal["client"].get(url + "gold/map?bbox=nan,0,10,10").status_code == 422
    assert portal["client"].get(url + "bronze/map").status_code == 422


def test_admin_grant_conflict_and_revocation(portal):
    viewer, _ = login(portal, subject="viewer")
    s = selection(portal).json()
    login(portal, subject="admin", role="Admin", layers=())
    url = f"/api/portal/v1/admin/users/{viewer['user_id']}/grants/{portal['did']}/gold"
    assert portal["client"].put(url, json={"actions": ["read"]}).status_code == 428
    assert (
        portal["client"]
        .put(url, json={"actions": ["read"]}, headers={"If-Match": "999"})
        .status_code
        == 412
    )
    assert (
        portal["client"].put(url, json={"actions": ["read"]}, headers={"If-Match": "1"}).status_code
        == 200
    )
    # New session, same identity; don't reseed grants after revocation.
    token, _ = portal["store"].user_login(portal["cfg"].oidc_issuer, "viewer", "viewer", "")
    portal["client"].cookies.set("portal_session", token)
    aid = s["layers"]["gold"]["artifacts"][0]["artifact_id"]
    assert (
        portal["client"]
        .get(f"/api/portal/v1/selections/{s['selection_id']}/artifacts/{aid}/download")
        .status_code
        == 403
    )


def test_atomic_grant_and_audit_failure(portal):
    user, _ = login(portal)
    login(portal, subject="admin", role="Admin", layers=())
    with portal["store"].db() as db:
        db.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON audit WHEN NEW.action='grant_updated' BEGIN SELECT RAISE(ABORT,'fault'); END"
        )
    url = f"/api/portal/v1/admin/users/{user['user_id']}/grants/{portal['did']}/gold"
    assert (
        portal["client"].put(url, json={"actions": ["read"]}, headers={"If-Match": "1"}).status_code
        == 503
    )
    assert "download" in portal["store"].actions(user["user_id"], portal["did"])["gold"]


def test_quota_and_concurrency_limits(portal):
    user, _ = login(portal)
    with portal["store"].db() as db:
        db.execute(
            "INSERT OR REPLACE INTO usage VALUES (?,?,?,?)",
            (user["user_id"], "metadata", int(time.time()) // 60, 120),
        )
    r = portal["client"].get("/api/portal/v1/overview")
    assert r.status_code == 429 and r.headers["Retry-After"]
    store = portal["store"]
    first = store.acquire(user["user_id"], "download", 2, 60)
    second = store.acquire(user["user_id"], "download", 2, 60)
    from server.portal.store import PortalError

    with pytest.raises(PortalError):
        store.acquire(user["user_id"], "download", 2, 60)
    store.release(first)
    store.release(second)


def test_release_root_and_integrity_guard(portal):
    with pytest.raises(ValueError):
        PortalConfig(storage_root=Path("data_lake/.test-runs/portal"))
    assert verify_release(portal["root"], "fixture-v1")["status"] == "complete"
    (portal["path"] / "serving/latest/table.json").write_text("[]")
    with pytest.raises(ValueError, match="checksum"):
        verify_release(portal["root"], "fixture-v1")


def test_unverified_current_never_uses_old_revision(portal):
    catalog_path = portal["path"] / "catalog.json"
    catalog = json.loads(catalog_path.read_text())
    catalog["observations"][-1]["status"] = "CORRUPT"
    catalog_path.write_text(json.dumps(catalog))
    info_path = portal["path"] / "release.json"
    info = json.loads(info_path.read_text())
    info["hashes"]["catalog.json"] = sha256(catalog_path)
    info_path.write_text(json.dumps(info))
    login(portal)
    assert selection(portal).json()["layers"]["bronze"]["availability"] == "unavailable"
