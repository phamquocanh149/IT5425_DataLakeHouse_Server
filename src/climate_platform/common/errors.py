"""Exception filter shared by every module.

Maps domain errors to HTTP responses and standardizes the ``{"detail": ...}`` payload
while keeping full compatibility with FastAPI/Starlette ``HTTPException`` handling.
"""

from fastapi import HTTPException
from starlette.responses import JSONResponse


async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers=exc.headers,
    )


def register_exception_handlers(app) -> None:
    """Install the application-wide exception filters on ``app``."""
    app.add_exception_handler(HTTPException, http_exception_handler)
