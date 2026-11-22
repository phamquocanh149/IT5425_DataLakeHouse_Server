"""Deterministic test configuration; never authenticate with workstation credentials."""

import os
import sys
from pathlib import Path
from uuid import uuid4

# Resolve the package from the checkout even without an editable install in local runs.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def pytest_configure(config):
    if config.option.basetemp is None:
        parent = config.rootpath / ".test-runs"
        parent.mkdir(exist_ok=True)
        config.option.basetemp = str(parent / uuid4().hex)


os.environ.update(
    STORAGE_BACKEND="local",
    API_KEYS="[]",
    ENABLE_STATIC_KEYS="True",
    REQUIRE_SSE_KMS="False",
    REQUIRE_OBJECT_LOCK="False",
    RATE_LIMIT_PER_MINUTE="120",
    DAILY_UPLOAD_QUOTA_BYTES="1073741824",
    SQLITE_BUSY_TIMEOUT_SECONDS="0.5",
    READINESS_CACHE_SECONDS="3",
    READINESS_TIMEOUT_SECONDS="0.5",
    DEBUG="False",
    COLLECTOR_API_KEY="test-only-collector",
    ADMIN_API_KEY="test-only-admin",
    CLIENT01_API_KEY="test-only-client01",
    CLIENT02_API_KEY="test-only-client02",
    ENABLE_LEGACY_KEYS="False",
    COLLECTOR_SOURCES='["usdm","noaa","usgs","nldas"]',
)
