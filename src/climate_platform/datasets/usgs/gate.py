"""USGS medallion eligibility gate.

One job: compose the eligibility questions ("Bronze validated?", "raw archive audited?") with
the shared ``AllOf``/``FunctionGate`` contract. Eligibility is evaluated over the
client-provided Bronze the Server reads; the first failure explains why and a gate never
writes medallion data.
"""

from __future__ import annotations

from climate_platform.datasets.usgs.preprocess import audit_raw
from climate_platform.datasets.usgs.validate import validate
from climate_platform.medallion.contracts import Readiness
from climate_platform.medallion.gate import AllOf, FunctionGate


def _bronze_readiness(cfg) -> Readiness:
    report = validate(cfg)
    if not report["all_jobs_successful"]:
        unresolved = len(report["unresolved_jobs"])
        return Readiness(
            False,
            f"Bronze incomplete: {report['unplanned_jobs']} unplanned, {unresolved} unresolved jobs",
        )
    return Readiness(True, "")


def _raw_audit_readiness(cfg) -> Readiness:
    audit = audit_raw(cfg)
    if not audit["passed"]:
        return Readiness(False, f"raw audit failed: {len(audit['issues'])} issues")
    return Readiness(True, "")


def conditions_met(cfg) -> Readiness:
    return AllOf(
        [
            FunctionGate(lambda: _bronze_readiness(cfg)),
            FunctionGate(lambda: _raw_audit_readiness(cfg)),
        ]
    ).check()
