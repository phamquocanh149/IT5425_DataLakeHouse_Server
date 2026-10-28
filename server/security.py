import logging
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from server.config import settings

logger = logging.getLogger("climate_server.security")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


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
        logger.warning("Authentication failed: Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.debug("Client authenticated successfully as '%s'", client_id)
    return client_id


def allowed_sources(client_id):
    return {"collector01": settings.COLLECTOR_SOURCES,
            "client01": {"usdm", "noaa"}, "client02": {"usgs", "nldas"}}.get(client_id, set())


def authorize_upload(client_id, source):
    if source.strip().lower() not in settings.ALLOWED_SOURCES:
        raise HTTPException(400, "Invalid source")
    if source.strip().lower() not in allowed_sources(client_id):
        raise HTTPException(403, "Identity is not authorized to upload this source")
