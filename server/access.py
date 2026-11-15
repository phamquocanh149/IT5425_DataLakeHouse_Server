"""Authenticate before multipart parsing; persistent, atomic bandwidth and request limits."""

import hashlib
import hmac
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from .config import settings

audit = logging.getLogger("climate_server.audit")


def authenticate(token):
    digest = hashlib.sha256((token or "").encode()).hexdigest()
    key_id, separator, secret = (token or "").partition(".")
    secret_digest = hashlib.sha256(secret.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    identity = None
    for record in settings.API_KEYS:
        matches = hmac.compare_digest(secret_digest, record.secret_hash)
        if (
            matches
            and separator
            and key_id == record.key_id
            and record.enabled
            and now < record.expires_at
            and (record.not_before is None or now >= record.not_before)
        ):
            identity = (record.client_id, record.key_id)
    if settings.ENABLE_STATIC_KEYS:
        for raw, client in settings.api_keys.items():
            if hmac.compare_digest(digest, hashlib.sha256(raw.encode()).hexdigest()):
                identity = (client, "static-" + client)
    if identity is None:
        raise HTTPException(
            401, "Missing or invalid API key", headers={"WWW-Authenticate": "ApiKey"}
        )
    return identity


def initialize_access_store():
    settings.metadata_path.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.metadata_path / "access.sqlite3", timeout=0.5)
    try:
        db.execute(
            "CREATE TABLE IF NOT EXISTS usage (key_id TEXT PRIMARY KEY, minute INTEGER, requests INTEGER, day INTEGER, bytes INTEGER)"
        )
        db.commit()
    finally:
        db.close()


def access_probe():
    db = sqlite3.connect(
        (settings.metadata_path / "access.sqlite3").resolve().as_uri() + "?mode=rw",
        uri=True,
        timeout=settings.READINESS_TIMEOUT_SECONDS,
    )
    try:
        db.execute("SELECT key_id FROM usage LIMIT 1").fetchone()
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE usage SET requests=requests WHERE 0")
        db.rollback()
    finally:
        db.close()


def charge(key_id, *, size=0, request=False, client_id=None):
    """Count all received upload bytes (including failed uploads/retries), UTC day.

    SQLite serialization makes limits effective across processes and restarts.
    Only authenticated IDs reach this table, preventing unbounded attacker keys.
    """
    db = sqlite3.connect(
        (settings.metadata_path / "access.sqlite3").resolve().as_uri() + "?mode=rw",
        uri=True,
        timeout=0.5,
    )
    now = int(time.time())
    minute, day = now // 60, now // 86400
    try:
        db.execute("BEGIN IMMEDIATE")
        buckets = ["key:" + key_id]
        if client_id:
            buckets.append("client:" + client_id)
        for bucket_id in buckets:
            row = db.execute(
                "SELECT minute, requests, day, bytes FROM usage WHERE key_id=?", (bucket_id,)
            ).fetchone()
            requests = row[1] if row and row[0] == minute else 0
            used = row[3] if row and row[2] == day else 0
            if request and requests >= settings.RATE_LIMIT_PER_MINUTE:
                raise HTTPException(
                    429, "Request rate exceeded", headers={"Retry-After": str(60 - now % 60)}
                )
            if used + size > settings.DAILY_UPLOAD_QUOTA_BYTES:
                raise HTTPException(
                    429,
                    "Daily upload quota exceeded",
                    headers={"Retry-After": str(86400 - now % 86400)},
                )
            db.execute(
                "INSERT OR REPLACE INTO usage VALUES (?,?,?,?,?)",
                (bucket_id, minute, requests + int(request), day, used + size),
            )
        db.commit()
    finally:
        db.close()


class AccessMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") not in {"/upload", "/uploads"}:
            return await self.app(scope, receive, send)
        code, client_id, key_id = 500, None, None
        sent = False
        total = 0

        async def audited_send(message):
            nonlocal code, sent
            if message["type"] == "http.response.start":
                code, sent = message["status"], True
            await send(message)

        async def limited_receive():
            nonlocal total
            message = await receive()
            if scope["path"].rstrip("/") == "/upload" and message["type"] == "http.request":
                size = len(message.get("body", b""))
                total += size
                if total > settings.MAX_FILE_SIZE_BYTES + 1024 * 1024:
                    raise HTTPException(413, "Request body too large")
                try:
                    await run_in_threadpool(charge, key_id, size=size, client_id=client_id)
                except sqlite3.Error:
                    raise HTTPException(503, "Access accounting unavailable") from None
            return message

        try:
            headers = [v for k, v in scope["headers"] if k.lower() == b"x-api-key"]
            if len(headers) != 1:
                raise HTTPException(401, "Missing or ambiguous API key")
            client_id, key_id = authenticate(headers[0].decode("latin-1"))
            scope.setdefault("state", {})["authenticated_client"] = client_id
            try:
                await run_in_threadpool(charge, key_id, request=True, client_id=client_id)
            except sqlite3.Error:
                raise HTTPException(503, "Access accounting unavailable") from None
            await self.app(scope, limited_receive, audited_send)
        except HTTPException as exc:
            if sent:
                raise
            await JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
            )(scope, receive, audited_send)
        finally:
            # No secrets, filenames, query strings or raw user-controlled headers.
            audit.info(
                json.dumps(
                    {
                        "event": "api_access",
                        "at": datetime.now(timezone.utc).isoformat(),
                        "client_id": client_id,
                        "key_id": key_id,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": code,
                        "received_bytes": total,
                    }
                )
            )
