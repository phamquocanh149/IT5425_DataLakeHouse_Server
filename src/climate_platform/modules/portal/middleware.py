"""Portal request middleware orchestrator.

Composes the one-job admission helpers (``request_policy``) with the transport concerns:
request-id, error mapping, preview-lease release, security headers (``headers``), denial
audit and request logging. Authorization policy is applied by guards in the authorization
module, not here.
"""

import logging
import secrets
import sqlite3
import time

import httpx
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from climate_platform.modules.portal.errors import PortalError, error_response
from climate_platform.modules.portal.headers import apply_security_headers
from climate_platform.modules.portal.request_policy import (
    PREFIX,
    admit,
    enforce_demo_loopback,
)

__all__ = ["PREFIX", "portal_access"]

logger = logging.getLogger("climate_platform.portal")


def portal_access(config, store):
    async def middleware(request: Request, call_next):
        path = request.url.path
        if not path.startswith((PREFIX, "/portal")):
            return await call_next(request)
        request.state.request_id = secrets.token_hex(12)
        lease = None
        actor = None
        started = time.monotonic()
        try:
            enforce_demo_loopback(config, request)
            if path.startswith(PREFIX):
                actor, lease = await admit(store, request, config, path)
            response = await call_next(request)
        except PortalError as exc:
            response = error_response(exc, request.state.request_id)
        except (
            OSError,
            sqlite3.Error,
            SQLAlchemyError,
            httpx.HTTPError,
            KeyError,
            ValueError,
        ) as exc:
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
        apply_security_headers(response, request.state.request_id)
        if path.startswith(PREFIX) and response.status_code >= 400:
            await run_in_threadpool(
                store.record_audit,
                actor,
                "api_denied",
                None,
                str(response.status_code),
                request.state.request_id,
            )
        logger.info(
            "portal status=%s duration_ms=%.0f request_id=%s",
            response.status_code,
            (time.monotonic() - started) * 1000,
            request.state.request_id,
        )
        return response

    return middleware
