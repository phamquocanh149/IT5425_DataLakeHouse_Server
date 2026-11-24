"""USGS Bronze contract: the normalized daily-discharge Parquet schema.

One job: define the schema of the normalized Bronze partitions (``normalized/region=/year=``)
that every USGS medallion stage reads. Bronze is provided by the Client — either through the
platform upload registry or by placing the snapshots the reference crawler
(``scripts/process_data/usgs/crawl_usgs.py``) produces. The Server never fetches upstream.
"""

from __future__ import annotations

import pyarrow as pa

SCHEMA = pa.schema(
    [
        ("observation_id", pa.string()),
        ("site_id", pa.string()),
        ("site_number", pa.string()),
        ("date", pa.string()),
        ("discharge_cfs", pa.float64()),
        ("raw_value", pa.string()),
        ("unit", pa.string()),
        ("parameter_code", pa.string()),
        ("statistic_id", pa.string()),
        ("time_series_id", pa.string()),
        ("approval_status", pa.string()),
        ("qualifier", pa.string()),
        ("last_modified", pa.string()),
        ("region", pa.string()),
        ("year", pa.int32()),
        ("invalid_numeric", pa.bool_()),
        ("unexpected_unit", pa.bool_()),
        ("conflict", pa.bool_()),
    ]
)
