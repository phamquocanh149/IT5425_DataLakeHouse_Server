"""Mount Portal routes in the existing FastAPI application, or a loopback demo."""

import logging
import secrets
import sqlite3
import time

import httpx
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from .api import api_router
from .auth import auth_router
from .store import Store, PortalError

PREFIX = "/api/portal/v1"
logger = logging.getLogger("climate_server.portal")


def error_response(exc, request_id):
    headers = {"Cache-Control": "private, no-store", "X-Request-ID": request_id}
    if exc.status == 429:
        headers["Retry-After"] = "60"
    return JSONResponse(
        {
            "error": {"code": exc.code, "message": exc.message},
            "retryable": exc.status in {429, 503},
            "request_id": request_id,
        },
        status_code=exc.status,
        headers=headers,
    )


def install_portal(app, config):
    store = Store(config.storage_root)
    store.initialize()
    app.state.portal_config = config
    app.state.portal_store = store

    @app.exception_handler(PortalError)
    async def handle_portal_error(request: Request, exc: PortalError):
        return error_response(exc, getattr(request.state, "request_id", secrets.token_hex(8)))

    previous_validation = app.exception_handlers.get(RequestValidationError)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc):
        if request.url.path.startswith(PREFIX):
            return error_response(PortalError(422, "INVALID_FILTER"), request.state.request_id)
        if previous_validation:
            return await previous_validation(request, exc)
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.middleware("http")
    async def portal_access(request: Request, call_next):
        path = request.url.path
        if not path.startswith((PREFIX, "/portal", "/demo-idp")):
            return await call_next(request)
        request.state.request_id = secrets.token_hex(12)
        lease = None
        actor = None
        started = time.monotonic()
        try:
            # Explicit demo only; forwarded headers cannot elevate remote callers.
            if config.demo:
                if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
                    raise PortalError(403, "LOOPBACK_DEMO_ONLY")
                if request.url.hostname not in {"127.0.0.1", "localhost", "testserver"}:
                    raise PortalError(403, "LOOPBACK_DEMO_ONLY")
            if path.startswith(PREFIX):
                if path in {PREFIX + "/auth/login", PREFIX + "/auth/callback"}:
                    await run_in_threadpool(
                        store.limit,
                        "auth:" + (request.client.host if request.client else "unknown"),
                        "metadata",
                    )
                else:
                    user = await run_in_threadpool(
                        store.session, request.cookies.get("portal_session"), config
                    )
                    request.state.portal_user = user
                    actor = user["user_id"]
                    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                        if request.headers.get("origin") != config.origin.rstrip(
                            "/"
                        ) or not secrets.compare_digest(
                            request.headers.get("x-csrf-token", ""), user["csrf"]
                        ):
                            raise PortalError(403, "CSRF_FAILED")
                        length = request.headers.get("content-length")
                        if length and (not length.isdigit() or int(length) > 16384):
                            raise PortalError(413, "REQUEST_TOO_LARGE")
                        body = bytearray()
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > 16384:
                                raise PortalError(413, "REQUEST_TOO_LARGE")
                        request._body = bytes(body)
                    category = "preview" if path.endswith(("/preview", "/map")) else "metadata"
                    await run_in_threadpool(store.limit, actor, category)
                    if category == "preview":
                        lease = await run_in_threadpool(store.acquire, actor, "preview", 4, 10)
            response = await call_next(request)
        except PortalError as exc:
            response = error_response(exc, request.state.request_id)
        except (OSError, sqlite3.Error, httpx.HTTPError, KeyError, ValueError) as exc:
            logger.error(
                "Portal request failed request_id=%s type=%s",
                request.state.request_id,
                type(exc).__name__,
            )
            response = error_response(
                PortalError(503, "STORAGE_UNAVAILABLE"), request.state.request_id
            )
        finally:
            if lease:
                await run_in_threadpool(store.release, lease)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if path.startswith(PREFIX) and response.status_code >= 400:

            def audit_denial():
                with store.db() as db:
                    store.audit(
                        db,
                        actor,
                        "api_denied",
                        None,
                        str(response.status_code),
                        request.state.request_id,
                    )

            await run_in_threadpool(audit_denial)
        logger.info(
            "portal status=%s duration_ms=%.0f request_id=%s",
            response.status_code,
            (time.monotonic() - started) * 1000,
            request.state.request_id,
        )
        return response

    app.include_router(auth_router(config, store), prefix=PREFIX)
    app.include_router(api_router(config, store), prefix=PREFIX)

    assets = config.frontend_root / "assets"
    if assets.exists():
        app.mount("/portal/assets", StaticFiles(directory=assets), name="portal-assets")

    @app.get("/portal", include_in_schema=False)
    def portal_redirect():
        return RedirectResponse("/portal/")

    @app.get("/portal/{route:path}", include_in_schema=False)
    def portal_shell(route: str):
        path = config.frontend_root / "index.html"
        if not path.is_file():
            raise PortalError(503, "FRONTEND_NOT_BUILT")
        return FileResponse(path)

    return store
