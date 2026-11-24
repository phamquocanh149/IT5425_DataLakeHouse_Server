"""Processing engine: resolve a dataset processor and run it.

The engine is intentionally thin. It owns processor lookup and delegates every
dataset-specific step to the DatasetProcessor implementation, so a new dataset is
added by registering a strategy rather than editing this module.
"""

from typing import Callable, Dict

from climate_platform.modules.processing.contracts import (
    DatasetProcessor,
    ProcessorConfig,
    ProcessingReport,
)


def run_pipeline(processor: DatasetProcessor, config: ProcessorConfig) -> ProcessingReport:
    """Run one dataset processor end to end and return its report."""
    if config.source != processor.source:
        raise ValueError("Processor source does not match the requested config")
    return processor.run(config)


class ProcessorRegistry:
    """Simple explicit registry; no import-time magic or third-party DI framework."""

    def __init__(self):
        self._factories: Dict[str, Callable[[], DatasetProcessor]] = {}

    def register(self, source: str, factory: Callable[[], DatasetProcessor]) -> None:
        self._factories[source] = factory

    def get(self, source: str) -> DatasetProcessor:
        try:
            return self._factories[source]()
        except KeyError:
            raise ValueError(f"No dataset processor registered for '{source}'") from None

    def sources(self) -> tuple:
        return tuple(sorted(self._factories))


def default_registry() -> ProcessorRegistry:
    """Register every dataset processor shipped with the Server."""
    from climate_platform.datasets.nldas.processor import NldasProcessor
    from climate_platform.datasets.noaa.processor import NoaaProcessor
    from climate_platform.datasets.usgs.processor import UsgsProcessor
    from climate_platform.datasets.usdm.processor import UsdmProcessor

    registry = ProcessorRegistry()
    registry.register("usdm", UsdmProcessor)
    registry.register("noaa", NoaaProcessor)
    registry.register("usgs", UsgsProcessor)
    registry.register("nldas", NldasProcessor)
    return registry
