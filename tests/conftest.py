"""Deterministic test configuration; never authenticate with workstation credentials."""

import os
from uuid import uuid4


def pytest_configure(config):
    if config.option.basetemp is None:
        parent = config.rootpath / ".test-runs"
        parent.mkdir(exist_ok=True)
        config.option.basetemp = str(parent / uuid4().hex)


os.environ.update(
    STORAGE_BACKEND="local",
    DEBUG="False",
    COLLECTOR_API_KEY="test-only-collector",
    ADMIN_API_KEY="test-only-admin",
    CLIENT01_API_KEY="test-only-client01",
    CLIENT02_API_KEY="test-only-client02",
    ENABLE_LEGACY_KEYS="False",
    COLLECTOR_SOURCES='["usdm","noaa","usgs","nldas"]',
)
