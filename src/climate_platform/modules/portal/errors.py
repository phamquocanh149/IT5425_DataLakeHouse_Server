"""Portal HTTP error filter (standardized portal error payload).

The ``PortalError`` domain type is defined in ``common.errors`` (shared, downward-only
dependency); this module re-exports it and owns only the HTTP response shaping.
"""

from starlette.responses import JSONResponse

from climate_platform.common.errors import PortalError

__all__ = ["PortalError", "error_response"]


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
