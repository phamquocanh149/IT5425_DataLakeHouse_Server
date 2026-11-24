"""NOAA/CPC teleconnection dataset processor (Strategy for the processing engine).

Thin adapter over the NOAA medallion package: it resolves a context, exposes readiness and
delegates the Silver -> Gold run to ``datasets.noaa.pipeline``. It contains no science and no
``sys.path`` reach into the checkout scripts; the science lives in ``silver``/``gold``.
"""

from __future__ import annotations

import logging

from climate_platform.medallion.contracts import Readiness
from climate_platform.modules.processing.contracts import (
    DatasetProcessor,
    ProcessorConfig,
    ProcessingReport,
)

logger = logging.getLogger("climate_platform.noaa")


class NoaaProcessor(DatasetProcessor):
    """NOAA weekly teleconnection processor: readiness plan plus medallion execution."""

    source = "noaa"

    def __init__(
        self,
        bronze_root=None,
        silver_root=None,
        gold_root=None,
        week_dates_csv=None,
        usdm_csv=None,
    ):
        self.bronze_root = bronze_root
        self.silver_root = silver_root
        self.gold_root = gold_root
        self.week_dates_csv = week_dates_csv
        self.usdm_csv = usdm_csv

    def _context(self, config: ProcessorConfig | None = None):
        from climate_platform.datasets.noaa import pipeline

        overrides = {
            "bronze_root": self.bronze_root,
            "silver_root": self.silver_root,
            "gold_root": self.gold_root,
            "week_dates_csv": self.week_dates_csv,
            "usdm_csv": self.usdm_csv,
        }
        if config is not None:
            if config.source_root:
                overrides["bronze_root"] = config.source_root
            if config.output_root:
                overrides["silver_root"] = config.output_root
        return pipeline, pipeline.default_context(**overrides)

    def discover(self, start=None, end=None) -> Readiness:
        from climate_platform.datasets.noaa import pipeline

        context = self._context()[1]
        report = pipeline.plan(context)
        details = {
            key: report.details[key]
            for key in ("snapshot", "calendar", "silver_present", "gold_present")
        }
        return Readiness(report.ready, report.reason, {"source": self.source, **details})

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
