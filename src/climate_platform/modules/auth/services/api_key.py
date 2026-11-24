"""Collector API-key authentication ("who are you"). Authorization lives in the
``authorization`` module; this only resolves an API key to a client identity."""

import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import HTTPException

from climate_platform.config import settings


def authenticate(token):
    digest = hashlib.sha256((token or "").encode()).hexdigest()
    key_id, separator, secret = (token or "").partition(".")
    secret_digest = hashlib.sha256(secret.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    identity = None
    for record in settings.API_KEYS:
        matches = hmac.compare_digest(secret_digest, record.secret_hash)
        if (
            matches
            and separator
            and key_id == record.key_id
            and record.enabled
            and now < record.expires_at
            and (record.not_before is None or now >= record.not_before)
        ):
            identity = (record.client_id, record.key_id)
    if settings.ENABLE_STATIC_KEYS:
        for raw, client in settings.api_keys.items():
            if hmac.compare_digest(digest, hashlib.sha256(raw.encode()).hexdigest()):
                identity = (client, "static-" + client)
    if identity is None:
        raise HTTPException(
            401, "Missing or invalid API key", headers={"WWW-Authenticate": "ApiKey"}
        )
    return identity
