"""Access accounting repository (``metadata/access.sqlite3``).

Rate-limit and quota counters are serialized through SQLite so limits stay effective
across processes and restarts. Only authenticated IDs reach this table.

Statements are ORM constructs; the SQLite upsert mirrors ``INSERT OR REPLACE`` on
``key_id`` and ``BEGIN IMMEDIATE`` stays an explicit driver call (transaction control).
"""

import time

from fastapi import HTTPException
from sqlalchemy import false, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from climate_platform.config import settings
from climate_platform.entity import access as _access  # noqa: F401  (populate metadata)
from climate_platform.entity.access import AccessBase, AccessUsage
from climate_platform.repositories.database import connection, engine_for


def _access_path():
    return settings.metadata_path / "access.sqlite3"


def initialize_access_store():
    settings.metadata_path.mkdir(parents=True, exist_ok=True)
    engine_for(_access_path(), mode="rwc", busy_timeout=0.5)
    AccessBase.metadata.create_all(engine_for(_access_path(), mode="rwc", busy_timeout=0.5))


def access_probe():
    with connection(
        _access_path(), mode="rw", busy_timeout=settings.READINESS_TIMEOUT_SECONDS
    ) as db:
        db.execute(select(AccessUsage.key_id).limit(1)).first()
        # Detect a writer lock/read-only volume without changing persisted data.
        db.execute("BEGIN IMMEDIATE")
        db.execute(update(AccessUsage).values(requests=AccessUsage.requests).where(false()))
        db.rollback()


def charge(key_id, *, size=0, request=False, client_id=None):
    """Count all received upload bytes (including failed uploads/retries), UTC day.

    SQLite serialization makes limits effective across processes and restarts.
    Only authenticated IDs reach this table, preventing unbounded attacker keys.
    """
    now = int(time.time())
    minute, day = now // 60, now // 86400
    with connection(_access_path(), mode="rw", busy_timeout=0.5) as db:
        db.execute("BEGIN IMMEDIATE")
        buckets = ["key:" + key_id]
        if client_id:
            buckets.append("client:" + client_id)
        for bucket_id in buckets:
            row = (
                db.execute(
                    select(
                        AccessUsage.minute,
                        AccessUsage.requests,
                        AccessUsage.day,
                        AccessUsage.bytes,
                    ).where(AccessUsage.key_id == bucket_id)
                )
                .mappings()
                .first()
            )
            requests = row["requests"] if row and row["minute"] == minute else 0
            used = row["bytes"] if row and row["day"] == day else 0
            if request and requests >= settings.RATE_LIMIT_PER_MINUTE:
                raise HTTPException(
                    429, "Request rate exceeded", headers={"Retry-After": str(60 - now % 60)}
                )
            if used + size > settings.DAILY_UPLOAD_QUOTA_BYTES:
                raise HTTPException(
                    429,
                    "Daily upload quota exceeded",
                    headers={"Retry-After": str(86400 - now % 86400)},
                )
            db.execute(
                sqlite_insert(AccessUsage)
                .values(
                    key_id=bucket_id,
                    minute=minute,
                    requests=requests + int(request),
                    day=day,
                    bytes=used + size,
                )
                .on_conflict_do_update(
                    index_elements=[AccessUsage.key_id],
                    set_={
                        "minute": minute,
                        "requests": requests + int(request),
                        "day": day,
                        "bytes": used + size,
                    },
                )
            )
        db.commit()
