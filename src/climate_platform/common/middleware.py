"""Application-level middleware.

``AccessMiddleware`` gates the collector upload endpoints: it authenticates the caller
*before* multipart parsing and enforces persistent, atomic bandwidth and request limits
that survive restarts and are effective across processes (SQLite serialization).

The middleware is foundation-level: it holds no feature or repository import. The
authentication and accounting ports (``authenticate``/``charge``) are injected by the
composition root (``app.py``), so this module never depends upward on ``modules.auth`` or
sideways on ``repositories``.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

audit = logging.getLogger("climate_platform.audit")

PROTECTED_PATHS = {"/upload", "/uploads"}


def _emit_audit(logger, *, client_id, key_id, method, path, status, received_bytes):
    # No secrets, filenames, query strings or raw user-controlled headers.
    logger.info(
        json.dumps(
            {
                "event": "api_access",
                "at": datetime.now(timezone.utc).isoformat(),
                "client_id": client_id,
                "key_id": key_id,
                "method": method,
                "path": path,
                "status": status,
                "received_bytes": received_bytes,
            }
        )
    )


class AccessMiddleware:
    """Authenticate collector requests and charge persistent rate/quota counters.

    ``authenticate(token)`` resolves an API key to ``(client_id, key_id)`` and
    ``charge(key_id, *, size=0, request=False, client_id=None)`` records usage; both are
    supplied by the composition root so this module keeps its dependency direction down.
    """

    def __init__(self, app, *, authenticate, charge, max_file_size_bytes):
        self.app = app
        self.authenticate = authenticate
        self.charge = charge
        self.max_file_size_bytes = max_file_size_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") not in PROTECTED_PATHS:
            return await self.app(scope, receive, send)

        code, client_id, key_id = 500, None, None
        sent = False
        total = 0
        pending = 0

        async def flush_bytes():
            """Charge the bytes buffered since the last flush in one writer transaction.

            Accumulating chunks keeps a single 1 MB-per-chunk upload from opening one SQLite
            write transaction per megabyte; the daily quota is still enforced, just at the end
            of the buffered body.
            """
            nonlocal pending
            if not pending:
                return
            size, pending = pending, 0
            try:
                await run_in_threadpool(self.charge, key_id, size=size, client_id=client_id)
            except SQLAlchemyError:
                raise HTTPException(503, "Access accounting unavailable") from None

        async def audited_send(message):
            nonlocal code, sent
            if message["type"] == "http.response.start":
                code, sent = message["status"], True
            await send(message)

        async def limited_receive():
            nonlocal total, pending
            message = await receive()
            if scope["path"].rstrip("/") == "/upload" and message["type"] == "http.request":
                size = len(message.get("body", b""))
                total += size
                if total > self.max_file_size_bytes + 1024 * 1024:
                    raise HTTPException(413, "Request body too large")
                pending += size
                if not message.get("more_body", False):
                    await flush_bytes()
            return message

        try:
            headers = [v for k, v in scope["headers"] if k.lower() == b"x-api-key"]
            if len(headers) != 1:
                raise HTTPException(401, "Missing or ambiguous API key")
            client_id, key_id = self.authenticate(headers[0].decode("latin-1"))
            scope.setdefault("state", {})["authenticated_client"] = client_id
            try:
                await run_in_threadpool(self.charge, key_id, request=True, client_id=client_id)
            except SQLAlchemyError:
                raise HTTPException(503, "Access accounting unavailable") from None
            await self.app(scope, limited_receive, audited_send)
        except HTTPException as exc:
            if sent:
                raise
            await JSONResponse(
                {"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers
            )(scope, receive, audited_send)
        finally:
            # Safety net: charge any bytes left when the body was not fully read (abort/
            # disconnect) so accounting still counts what was received.
            try:
                await flush_bytes()
            except HTTPException:
                pass
            _emit_audit(
                audit,
                client_id=client_id,
                key_id=key_id,
                method=scope["method"],
                path=scope["path"],
                status=code,
                received_bytes=total,
            )
