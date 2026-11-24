"""Authentication guard: resolve the collector identity (header API key, cached in
``request.state``). Authorization (role/grants/source) lives in the authorization module."""

from typing import Optional

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_client(
    request: Request, api_key: Optional[str] = Security(API_KEY_HEADER)
) -> str:
    from climate_platform.modules.auth.services.api_key import authenticate

    cached = getattr(request.state, "authenticated_client", None)
    return cached if cached is not None else authenticate(api_key)[0]
