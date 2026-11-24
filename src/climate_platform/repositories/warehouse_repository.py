"""SQLAlchemy warehouse repository for USDM builds/attempts/gold cells.

The warehouse database is local-only; it stores build lineage, per-week attempts and the
Gold projection used by the Portal release snapshot.
"""

from contextlib import contextmanager

from climate_platform.entity import warehouse as _warehouse  # noqa: F401  (populate metadata)
from climate_platform.entity.warehouse import GOLD_WEEKLY_VIEW, WarehouseBase
from climate_platform.repositories.database import connection, engine_for


def initialize_catalog(path):
    engine_for(path, mode="rwc")
    WarehouseBase.metadata.create_all(engine_for(path, mode="rwc"))
    with connection(path) as db:
        db.executescript(GOLD_WEEKLY_VIEW)


@contextmanager
def db(path, *, create=False):
    """Yield a warehouse connection that commits the transaction on success."""
    with connection(path, mode="rwc" if create else "rw") as conn:
        yield conn
        conn.commit()
