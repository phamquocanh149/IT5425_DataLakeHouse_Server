"""Medallion standard: the shared Bronze -> Silver -> Gold layered framework.

Each module owns exactly one concern:

- ``contracts`` — typed shapes/protocols (``Layer``, ``Readiness``, ``RunReport``, ``Gate``, ``Stage``)
- ``paths``     — resolve Bronze/Silver/Gold roots for a source
- ``io``        — atomic JSON write + checksum helpers
- ``lock``      — one cross-platform exclusive OS lock
- ``publisher`` — atomic, checksum-verified immutable product publication
- ``gate``      — eligibility composition (``AllOf``)
- ``runner``    — ordered stage execution under the lock

Datasets implement ``gate``/``silver``/``gold``/``pipeline`` under ``datasets/<source>/``
and never edit this package.
"""

from climate_platform.medallion.contracts import (
    Gate,
    Layer,
    Readiness,
    RunReport,
    Stage,
)
from climate_platform.medallion.gate import AllOf, FunctionGate
from climate_platform.medallion.io import atomic_replace, file_hash, read_json, write_json_atomic
from climate_platform.medallion.lock import exclusive_run
from climate_platform.medallion.paths import MedallionPaths
from climate_platform.medallion.publisher import product_path, publish_atomic
from climate_platform.medallion.runner import MedallionRunner

__all__ = [
    "AllOf",
    "FunctionGate",
    "Gate",
    "Layer",
    "MedallionPaths",
    "MedallionRunner",
    "Readiness",
    "RunReport",
    "Stage",
    "atomic_replace",
    "exclusive_run",
    "file_hash",
    "product_path",
    "publish_atomic",
    "read_json",
    "write_json_atomic",
]
