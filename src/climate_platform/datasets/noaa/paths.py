"""NOAA dataset paths and defaults.

One job: resolve where NOAA Bronze/Silver/Gold and the USDM Tuesday calendar live. Roots
come from ``MedallionPaths`` (``NOAA_BRONZE_ROOT``/``NOAA_SILVER_ROOT``/``NOAA_GOLD_ROOT``);
the calendar and lock file keep their own ``NOAA_WEEK_DATES_CSV``/``NOAA_LOCK_FILE`` overrides.
"""

from __future__ import annotations

import os
from pathlib import Path

from climate_platform.config import settings
from climate_platform.medallion.contracts import Layer
from climate_platform.medallion.paths import MedallionPaths

SOURCE = "noaa"
SERVER_ROOT = Path(settings.BASE_DIR)


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def roots() -> MedallionPaths:
    return MedallionPaths(SOURCE)


def bronze_root() -> Path:
    return roots().root(Layer.BRONZE)


def silver_root() -> Path:
    return roots().root(Layer.SILVER)


def gold_root() -> Path:
    return roots().root(Layer.GOLD)


def default_week_dates_csv() -> Path:
    return _env_path("NOAA_WEEK_DATES_CSV", gold_root() / "usdm_week_dates.csv")


def default_lock_file() -> Path:
    return _env_path("NOAA_LOCK_FILE", _scratch() / "noaa_medallion.lock")


def _scratch() -> Path:
    return Path(settings.BASE_DIR) / "data_lake" / "temp"
