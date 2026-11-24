"""Shared UTC clock helper.

One job: format the current UTC instant as an ISO-8601 string, so timestamp fields across
the medallion, crawl and warehouse code are produced the same way.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
