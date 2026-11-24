"""USGS crawl configuration.

One job: the validated ``Config`` for a USGS crawl (scope, concurrency, output root).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from climate_platform.datasets.usgs.paths import default_bronze_root


@dataclass
class Config:
    start: str = "2020-01-01"
    end: str = "2022-12-31"
    regions: tuple = tuple(f"{i:02d}" for i in range(1, 19))
    output: str = str(default_bronze_root())
    workers: int = 2
    requests_per_second: float = 0.25
    page_size: int = 1000
    retries: int = 6

    def check(self):
        if date.fromisoformat(self.start) > date.fromisoformat(self.end):
            raise ValueError("start must not exceed end")
        if (
            self.workers < 1
            or self.requests_per_second <= 0
            or self.page_size < 1
            or self.retries < 0
        ):
            raise ValueError("Invalid concurrency, rate, page size or retries")
        if not self.regions or not set(self.regions) <= {f"{i:02d}" for i in range(1, 19)}:
            raise ValueError("regions must be strings 01 through 18")
        return self
