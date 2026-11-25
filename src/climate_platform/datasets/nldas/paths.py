"""NLDAS dataset paths and defaults.

One job: resolve Bronze, references, Silver, Gold and the lock file. Silver/Gold come from
``MedallionPaths`` (data_lake/<layer>/nldas); Bronze and references default to the sibling
``duy-nldas-script`` workspace and keep their own env overrides.
"""

from __future__ import annotations

import os
from pathlib import Path

from climate_platform.config import settings
from climate_platform.medallion.contracts import Layer
from climate_platform.medallion.paths import MedallionPaths

SOURCE = "nldas"
HERE = Path(__file__).resolve()
# <repo>/src/climate_platform/datasets/nldas/paths.py -> <repo>
SERVER_ROOT = Path(settings.BASE_DIR)
WORKSPACE = HERE.parents[4]
DUY_ROOT = WORKSPACE / "duy-nldas-script"
# Reference grid/calendar shipped inside the package so an installed/worker runtime is
# self-contained (the workspace copy is only a development convenience).
RESOURCES = HERE.parent / "resources"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def default_bronze_root() -> Path:
    return _env_path("NLDAS_BRONZE_ROOT", DUY_ROOT / "src" / "bronze" / "data")


def default_references() -> Path:
    value = os.environ.get("NLDAS_REFERENCES_DIR")
    if value:
        return Path(value)
    workspace = DUY_ROOT / "src" / "references"
    return workspace if workspace.exists() else RESOURCES


def roots() -> MedallionPaths:
    return MedallionPaths(SOURCE)


def default_silver_root() -> Path:
    return roots().root(Layer.SILVER)


def default_gold_root() -> Path:
    return roots().root(Layer.GOLD)


def default_lock_file() -> Path:
    return _env_path("NLDAS_LOCK_FILE", SERVER_ROOT / "data_lake" / "temp" / "nldas_medallion.lock")
