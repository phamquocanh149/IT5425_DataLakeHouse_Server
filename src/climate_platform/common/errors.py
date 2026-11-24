"""Shared errors: the exception filter + the shared domain error.

Maps domain errors to HTTP responses and standardizes the ``{"detail": ...}`` payload
while keeping full compatibility with FastAPI/Starlette ``HTTPException`` handling.

``PortalError`` (status + code) is the portal domain error. It lives here, not in the
portal module, so the data layer and the authorization module can raise it without
importing ``modules.portal`` (the dependency direction stays downward).
"""

from fastapi import HTTPException
from starlette.responses import JSONResponse


class PortalError(Exception):
    def __init__(self, status, code, message=None):
        self.status, self.code = status, code
        self.message = message or code.replace("_", " ").capitalize()


async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers=exc.headers,
    )


def register_exception_handlers(app) -> None:
    """Install the application-wide exception filters on ``app``."""
    app.add_exception_handler(HTTPException, http_exception_handler)
