"""Deterministic test configuration; never authenticate with workstation credentials."""
import os

os.environ.update(DEBUG="False", COLLECTOR_API_KEY="test-only-collector",
                  ADMIN_API_KEY="test-only-admin", CLIENT01_API_KEY="test-only-client01",
                  CLIENT02_API_KEY="test-only-client02", ENABLE_LEGACY_KEYS="False",
                  COLLECTOR_SOURCES='["usdm","noaa","usgs","nldas"]')
