"""USDM dataset processor: facade over the one-job modules + engine adapter.

The replay logic lives in ``pipeline`` (orchestration), ``bronze`` (packaging),
``publisher`` (products), ``warehouse`` (rows) and ``worker`` (GIS subprocess). This module
re-exports the historical public names and provides the thin engine adapter.
"""

from __future__ import annotations

from pathlib import Path

from climate_platform.datasets.usdm.bronze import DATASET_KEY, package_raw
from climate_platform.datasets.usdm.pipeline import (
    MetadataManager,
    discover,
    exclusive_run,
    initialize_catalog,
    process_week,
    run_pipeline,
    run_worker,
    verify_products,
)
from climate_platform.datasets.usdm.worker import WORKER
from climate_platform.medallion.contracts import Readiness
from climate_platform.modules.processing.contracts import (
    DatasetProcessor,
    ProcessorConfig,
    ProcessingReport,
)

__all__ = [
    "DATASET_KEY",
    "MetadataManager",
    "UsdmProcessor",
    "WORKER",
    "discover",
    "exclusive_run",
    "initialize_catalog",
    "package_raw",
    "process_week",
    "run_pipeline",
    "run_worker",
    "verify_products",
]


class UsdmProcessor(DatasetProcessor):
    """USDM weekly GIS processor (Strategy for the processing engine).

    Delegates to the existing orchestration without changing discovery, validation,
    lineage, revision, checksum or Gold semantics.
    """

    source = "usdm"

    def __init__(self, source_root=None, output_root=None, python=None):
        self.source_root = source_root
        self.output_root = output_root
        self.python = python

    def discover(self, start=None, end=None) -> Readiness:
        try:
            weeks = discover(Path(self.source_root).resolve(), start, end)
        except ValueError as exc:
            return Readiness(False, str(exc), {"source": self.source})
        return Readiness(True, "", {"source": self.source, "weeks": len(weeks)})

    def run(self, config: ProcessorConfig | None = None) -> ProcessingReport:
        source = config.source_root if config else self.source_root
        output = config.output_root if config else self.output_root
        python = config.python if config else self.python
        start = config.start if config else None
        end = config.end if config else None
        report = run_pipeline(source, output, python, start, end)
        return ProcessingReport(
            succeeded=report["succeeded"],
            skipped=report["skipped"],
            failed=report["failed"],
            weeks=tuple(report["weeks"]),
        )
