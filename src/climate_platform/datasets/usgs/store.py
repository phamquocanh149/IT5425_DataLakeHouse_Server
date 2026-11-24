"""USGS Bronze checkpoint store.

One job: read the ``checkpoint.sqlite`` that records per-(site,year) Bronze job state and the
output-scope guard. It is written by the Client's reference crawler
(``scripts/process_data/usgs/crawl_usgs.py``) and read by every USGS medallion stage. This is
a pipeline-local process store inside the Bronze directory (not the platform
registry/warehouse), so it keeps the original direct sqlite3 access as a documented exception
to the package ORM rule; transaction control and DDL are explicitly allowed.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from climate_platform.common.clock import utc_now_iso

# Only these job columns may appear on the left of an ``UPDATE``: the column names are
# interpolated (SQLite cannot bind identifiers), so they are whitelisted rather than trusted
# from ``**values``. A future caller passing an unexpected key raises instead of injecting SQL.
JOB_COLUMNS = frozenset(
    {
        "site",
        "year",
        "region",
        "start",
        "end",
        "status",
        "error",
        "rows",
        "elapsed",
        "pages",
        "bytes",
        "updated",
    }
)


class Store:
    def __init__(self, config):
        self.config = config.check()
        self.root = Path(config.output)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "checkpoint.sqlite")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS jobs (
            site TEXT, year INTEGER, region TEXT, start TEXT, end TEXT,
            status TEXT DEFAULT 'pending', error TEXT, rows INTEGER DEFAULT 0,
            elapsed REAL, pages INTEGER DEFAULT 0, bytes INTEGER DEFAULT 0,
            updated TEXT, PRIMARY KEY(site,year));
        """)
        scope = json.dumps([config.start, config.end, sorted(config.regions)])
        old = self.db.execute("SELECT value FROM settings WHERE key='scope'").fetchone()
        if old and old[0] != scope:
            raise ValueError(
                "Output directory belongs to another date/region scope; choose a new output"
            )
        self.db.execute("INSERT OR IGNORE INTO settings VALUES ('scope',?)", (scope,))
        self.db.commit()

    def update(self, site, year, status, **values):
        values.update(status=status, updated=utc_now_iso())
        unknown = set(values) - JOB_COLUMNS
        if unknown:
            raise ValueError(f"Unknown job column(s): {sorted(unknown)}")
        self.db.execute(
            "UPDATE jobs SET " + ",".join(f"{k}=?" for k in values) + " WHERE site=? AND year=?",
            [*values.values(), site, year],
        )
        self.db.commit()

    def close(self):
        self.db.close()
