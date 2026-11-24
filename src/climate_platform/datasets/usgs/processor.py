"""USGS daily-discharge dataset processor (Strategy for the processing engine).

Thin adapter over the USGS medallion package: readiness is the Bronze validation plus the raw
archive audit; the run delegates Silver -> Weekly -> Gold to ``datasets.usgs.pipeline``. No
science and no ``sys.path`` reach into the checkout scripts.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from climate_platform.medallion.contracts import Readiness
from climate_platform.modules.processing.contracts import (
    DatasetProcessor,
    ProcessorConfig,
    ProcessingReport,
)

logger = logging.getLogger("climate_platform.usgs")


class UsgsProcessor(DatasetProcessor):
    """USGS retrospective streamflow processor: readiness plan plus medallion execution."""

    source = "usgs"

    def __init__(self, config_path=None, output=None, grid=None, wbd=None):
        self.config_path = config_path
        self.output = output
        self.grid = grid
        self.wbd = wbd

    def _config(self, config: ProcessorConfig | None = None):
        from climate_platform.datasets.usgs import pipeline

        values = {}
        if self.config_path is not None:
            values = tomllib.loads(Path(self.config_path).read_text())
        bronze = config.source_root if config and config.source_root else self.output
        if bronze is not None:
            values["output"] = str(bronze)
        return pipeline, pipeline.config_from_values(values)

    def _layout(self, pipeline):
        grid = self.grid if self.grid is not None else pipeline._default_grid()
        wbd = self.wbd if self.wbd is not None else pipeline._default_wbd()
        return grid, wbd

    def discover(self, start=None, end=None) -> Readiness:
        from climate_platform.datasets.usgs.gate import conditions_met

        _, cfg = self._config()
        readiness = conditions_met(cfg)
        return Readiness(readiness.ready, readiness.reason, {"source": self.source})

    def run(self, config: ProcessorConfig | None = None) -> ProcessingReport:
        pipeline, cfg = self._config(config)
        grid, wbd = self._layout(pipeline)
        report = pipeline.run(cfg, grid, wbd)
        planned, built, failures = report.planned, report.built, report.failures
        succeeded = sum(1 for stage in built if built[stage])
        failed = len(failures)
        skipped = sum(
            1 for stage in planned if planned[stage] and not built[stage] and stage not in failures
        )
        return ProcessingReport(succeeded=succeeded, skipped=skipped, failed=failed)
