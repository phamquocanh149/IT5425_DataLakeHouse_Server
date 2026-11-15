import logging
from typing import Optional
from fastapi import HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from server.config import settings

logger = logging.getLogger("climate_server.security")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_client(
    request: Request, api_key: Optional[str] = Security(API_KEY_HEADER)
) -> str:
    from server.access import authenticate

    cached = getattr(request.state, "authenticated_client", None)
    return cached if cached is not None else authenticate(api_key)[0]


def allowed_sources(client_id):
    for record in settings.API_KEYS:
        if record.client_id == client_id:
            return record.sources if record.role == "collector" else set()
    return {
        "collector01": settings.COLLECTOR_SOURCES,
        "client01": {"usdm", "noaa"},
        "client02": {"usgs", "nldas"},
    }.get(client_id, set())


def authorize_upload(client_id, source):
    if source.strip().lower() not in settings.ALLOWED_SOURCES:
        raise HTTPException(400, "Invalid source")
    if source.strip().lower() not in allowed_sources(client_id):
        raise HTTPException(403, "Identity is not authorized to upload this source")
