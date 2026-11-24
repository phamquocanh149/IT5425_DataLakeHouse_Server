"""NOAA eligibility gate.

One job: answer "may the NOAA medallion run for this snapshot?". The only condition is
that the chosen Bronze snapshot is complete; the USDM Tuesday calendar is a Gold-specific
input handled by planning, not a run gate.
"""

from __future__ import annotations

from climate_platform.datasets.noaa import bronze
from climate_platform.medallion.contracts import Readiness


class SnapshotGate:
    """Eligible when the selected Bronze snapshot holds the manifest and every kept file."""

    def __init__(self, snapshot_dir):
        self.snapshot_dir = snapshot_dir

    def check(self) -> Readiness:
        return bronze.inspect(self.snapshot_dir)
