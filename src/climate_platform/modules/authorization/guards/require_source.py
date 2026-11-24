"""Guard: allowed upload sources (authorization)."""

from fastapi import HTTPException

from climate_platform.config import settings
from climate_platform.modules.authorization.services.policy import allowed_sources


def authorize_upload(client_id, source):
    if source.strip().lower() not in settings.ALLOWED_SOURCES:
        raise HTTPException(400, "Invalid source")
    if source.strip().lower() not in allowed_sources(client_id):
        raise HTTPException(403, "Identity is not authorized to upload this source")
