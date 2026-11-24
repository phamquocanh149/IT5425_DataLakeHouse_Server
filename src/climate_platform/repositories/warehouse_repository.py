"""SQLAlchemy warehouse repository for USDM builds/attempts/gold cells.

The warehouse database is local-only; it stores build lineage, per-week attempts and the
Gold projection used by the Portal release snapshot.
"""

from contextlib import contextmanager

from sqlalchemy import select

from climate_platform.entity import warehouse as _warehouse  # noqa: F401  (populate metadata)
from climate_platform.entity.warehouse import Attempt, GOLD_WEEKLY_VIEW, WarehouseBase
from climate_platform.repositories.database import connection, engine_for


def initialize_catalog(path):
    engine_for(path, mode="rwc")
    WarehouseBase.metadata.create_all(engine_for(path, mode="rwc"))
    with connection(path) as db:
        db.executescript(GOLD_WEEKLY_VIEW)


def attempts(path, source_dates):
    """Newest-first processing attempts whose ``source_date`` is in ``source_dates``."""
    statement = (
        select(Attempt)
        .where(Attempt.source_date.in_(source_dates))
        .order_by(Attempt.created_at.desc(), Attempt.attempt_id.desc())
    )
    with connection(path, mode="ro") as db:
        return [dict(r) for r in db.execute(statement).mappings().all()]


@contextmanager
def db(path, *, create=False):
    """Yield a warehouse connection that commits the transaction on success."""
    with connection(path, mode="rwc" if create else "rw") as conn:
        yield conn
        conn.commit()
