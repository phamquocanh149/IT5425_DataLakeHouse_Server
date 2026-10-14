import logging
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from server.config import settings

logger = logging.getLogger("climate_server.security")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def mask_api_key(api_key: Optional[str]) -> str:
    """Mask API key for safe logging."""
    if not api_key:
        return "<None>"
    if len(api_key) <= 6:
        return "***"
    return f"{api_key[:3]}...{api_key[-3:]}"


async def get_current_client(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """Validate X-API-Key header and map strictly to authenticated client_id.

    Raises:
        HTTPException 401 if API key is missing or invalid.
    """
    if not api_key:
        logger.warning("Authentication failed: Missing X-API-Key header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header in request",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    client_id = settings.api_keys.get(api_key)
    if not client_id:
        logger.warning("Authentication failed: Invalid API key provided [%s]", mask_api_key(api_key))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.debug("Client authenticated successfully as '%s'", client_id)
    return client_id
