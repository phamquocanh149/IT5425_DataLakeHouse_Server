"""NLDAS dataset processor (Strategy for the processing engine).

Thin adapter over the NLDAS medallion package: readiness is the per-product reference-week
plan; the run delegates Silver -> Gold to ``datasets.nldas.pipeline``. No science here.
"""

from __future__ import annotations

import logging

from climate_platform.medallion.contracts import Readiness
from climate_platform.modules.processing.contracts import (
    DatasetProcessor,
    ProcessorConfig,
    ProcessingReport,
)

logger = logging.getLogger("climate_platform.nldas")


class NldasProcessor(DatasetProcessor):
    """NLDAS land-surface processor: readiness plan plus medallion execution."""

    source = "nldas"

    def __init__(
        self,
        product="both",
        bronze_root=None,
        references=None,
        silver_root=None,
        gold_root=None,
        keep_r25=False,
    ):
        self.product = product
        self.bronze_root = bronze_root
        self.references = references
        self.silver_root = silver_root
        self.gold_root = gold_root
        self.keep_r25 = keep_r25

    def _context(self, config: ProcessorConfig | None = None):
        from climate_platform.datasets.nldas import pipeline

        overrides = {
            "bronze_root": self.bronze_root,
            "references": self.references,
            "silver_root": self.silver_root,
            "gold_root": self.gold_root,
            "keep_r25": self.keep_r25,
        }
        if config is not None:
            if config.source_root:
                overrides["bronze_root"] = config.source_root
            if config.output_root:
                overrides["silver_root"] = config.output_root
        return pipeline, pipeline.default_context(self.product, **overrides)

    def discover(self, start=None, end=None) -> Readiness:
        pipeline, context = self._context()
        report = pipeline.plan(context)
        return Readiness(report.ready, report.reason, {"source": self.source})

    def run(self, config: ProcessorConfig | None = None) -> ProcessingReport:
        pipeline, context = self._context(config)
        report = pipeline.run(context)
        planned, built, failures = report.planned, report.built, report.failures
        succeeded = sum(1 for stage in built if built[stage])
        failed = len(failures)
        skipped = sum(
            1 for stage in planned if planned[stage] and not built[stage] and stage not in failures
        )
        return ProcessingReport(succeeded=succeeded, skipped=skipped, failed=failed)
