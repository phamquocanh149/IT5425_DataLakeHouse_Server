"""Eligibility gates: decide whether a medallion run may proceed.

One job: compose the boolean eligibility questions ("is Bronze complete?", "is the crawl
validated?") into a single ``Readiness``. A gate never writes data; the only side effect a
gate is allowed is refreshing its own report artifacts, which is the caller's choice.
"""

from __future__ import annotations

from typing import Callable, Iterable

from climate_platform.medallion.contracts import Readiness

__all__ = ["FunctionGate", "AllOf"]


class FunctionGate:
    """A gate backed by a zero-argument callable returning ``Readiness``."""

    def __init__(self, check: Callable[[], Readiness]):
        self._check = check

    def check(self) -> Readiness:
        return self._check()


class AllOf:
    """Eligible only when every child gate is eligible; the first failure explains why."""

    def __init__(self, gates: Iterable):
        self._gates = tuple(gates)

    def check(self) -> Readiness:
        details = {}
        for gate in self._gates:
            result = gate.check()
            details.update(dict(result.details))
            if not result.ready:
                return Readiness(False, result.reason, details)
        return Readiness(True, "", details)
