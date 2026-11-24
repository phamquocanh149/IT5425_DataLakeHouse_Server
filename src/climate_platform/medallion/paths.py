"""Medallion root resolution for one dataset source.

One job: answer "where does Bronze/Silver/Gold for source X live?". Resolution order per
layer is an explicit path, then the ``<SOURCE>_<LAYER>_ROOT`` environment variable, then
the workspace default ``<data_lake>/<layer>/<source>``. Dataset pipelines used to each
re-implement this with their own ``default_*_root`` copies.
"""

from __future__ import annotations

import os
from pathlib import Path

from climate_platform.medallion.contracts import Layer

__all__ = ["MedallionPaths"]


class MedallionPaths:
    """Resolved Bronze/Silver/Gold roots for a single ``source``."""

    def __init__(
        self,
        source: str,
        *,
        bronze: str | os.PathLike | None = None,
        silver: str | os.PathLike | None = None,
        gold: str | os.PathLike | None = None,
        base: str | os.PathLike | None = None,
    ):
        self.source = source
        self._base = Path(base) if base is not None else _default_base()
        self._explicit = {
            Layer.BRONZE: bronze,
            Layer.SILVER: silver,
            Layer.GOLD: gold,
        }

    def env_name(self, layer: Layer) -> str:
        return f"{self.source.upper()}_{layer.value.upper()}_ROOT"

    def root(self, layer: Layer) -> Path:
        explicit = self._explicit[layer]
        if explicit is not None:
            return Path(explicit)
        value = os.environ.get(self.env_name(layer))
        if value:
            return Path(value)
        return self._base / layer.value / self.source


def _default_base() -> Path:
    from climate_platform.config import settings

    return settings.local_data_dir
