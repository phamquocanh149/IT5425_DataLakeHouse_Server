"""Dataset processor contract (Strategy/Plugin).

A new dataset (NOAA, USGS, NLDAS) adds its own processor implementing this interface
without touching the processing engine, serving, or catalog code. Phase 1 wires only
the USDM processor; the remaining datasets are intentionally not built yet.

The engine drives discovery and per-unit processing; the processor owns dataset-specific
science, validation and product publishing through the Bronze registry.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProcessorConfig:
    """Execution inputs shared by every dataset processor."""

    source: str = "usdm"
    source_root: object = None  # pathlib.Path; typed loosely to stay dependency-free
    output_root: object = None
    python: object = None  # interpreter used for the isolated science worker
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class ProcessingReport:
    """Bounded, JSON-serializable run summary (no secrets, no payload bytes)."""

    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    weeks: tuple = ()

    def as_dict(self) -> dict:
        return {
            "succeeded": self.succeeded,
            "skipped": self.skipped,
            "failed": self.failed,
            "weeks": list(self.weeks),
        }


@runtime_checkable
class DatasetProcessor(Protocol):
    """Minimal interface the processing engine relies on."""

    source: str

    def discover(self, start: str | None = None, end: str | None = None) -> dict: ...

    def run(self, config: ProcessorConfig | None = None) -> ProcessingReport: ...
