"""Processing module wiring: register dataset processors (default registry)."""

from climate_platform.modules.processing.engine import ProcessorRegistry, default_registry

__all__ = ["ProcessorRegistry", "default_registry"]
