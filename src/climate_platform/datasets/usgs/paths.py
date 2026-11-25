"""USGS dataset paths: medallion roots and the Bronze normalized layout.

One job: resolve where USGS Bronze/Silver/Gold and normalized job files live. Roots come
from ``MedallionPaths`` (``USGS_BRONZE_ROOT``/``USGS_SILVER_ROOT``/``USGS_GOLD_ROOT``);
``job_path`` is the Bronze normalized-partition layout shared by every USGS stage.
"""

from __future__ import annotations

from pathlib import Path

from climate_platform.medallion.contracts import Layer
from climate_platform.medallion.paths import MedallionPaths

SOURCE = "usgs"


def roots() -> MedallionPaths:
    return MedallionPaths(SOURCE)


def default_bronze_root() -> Path:
    return roots().root(Layer.BRONZE)


def default_silver_root() -> Path:
    return roots().root(Layer.SILVER)


def default_gold_root() -> Path:
    return roots().root(Layer.GOLD)


def resolve_roots(cfg):
    """Explicit Silver/Gold roots from a checked Config, falling back to env defaults."""
    silver = Path(cfg.silver_root) if cfg.silver_root else default_silver_root()
    gold = Path(cfg.gold_root) if cfg.gold_root else default_gold_root()
    return silver, gold


def job_path(root, job):
    """Normalized daily Parquet path for one (region, year, site) job."""
    return (
        root
        / "normalized"
        / f"region={job['region']}"
        / f"year={job['year']}"
        / f"{job['site']}.parquet"
    )
