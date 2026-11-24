"""Typed contracts for the Bronze -> Silver -> Gold medallion standard.

Pure data shapes and protocols only: no filesystem, no science, no IO. Every dataset
pipeline and the shared runner depend on this module, so it stays dependency-free and
stable. A dataset plugs in by implementing ``Stage`` objects and a ``Gate``; it never
edits the runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable


class Layer(str, Enum):
    """The three medallion layers every dataset shares."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


@dataclass(frozen=True)
class Readiness:
    """Eligibility of one data unit: whether the pipeline may run and why."""

    ready: bool
    reason: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@runtime_checkable
class Gate(Protocol):
    """Decides whether the medallion is eligible to run. No side effects on data."""

    def check(self) -> Readiness: ...


@runtime_checkable
class Stage(Protocol):
    """One medallion step: a named transformation that publishes one artifact.

    ``is_complete`` answers idempotency ("already built, skip"); ``build`` performs the
    transformation and returns the published artifact path (or ``None`` when skipped).
    A stage owns exactly one layer concern and no orchestration.
    """

    name: str
    layer: Layer

    def is_complete(self) -> bool: ...

    def build(self) -> str | None: ...


@dataclass
class RunReport:
    """Result of planning and executing a medallion run, shared by every dataset.

    ``planned``/``built``/``skipped`` are keyed by stage name; ``failures`` maps a stage
    name to its error text. ``details`` carries dataset-specific, JSON-safe context
    (snapshot path, calendar label, per-product week lists). No secrets, no payload bytes.
    """

    source: str
    ready: bool = False
    reason: str = ""
    dry_run: bool = False
    generated_at: str = ""
    planned: dict = field(default_factory=dict)
    built: dict = field(default_factory=dict)
    skipped: dict = field(default_factory=dict)
    failures: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)
    weeks: list = field(default_factory=list)

    def ok(self) -> bool:
        return not self.failures

    def exit_code(self) -> int:
        return 1 if self.failures else 0

    def as_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "source": self.source,
            "dry_run": self.dry_run,
            "ready": self.ready,
            "reason": self.reason,
            "planned": self.planned,
            "built": self.built,
            "skipped": self.skipped,
            "failures": self.failures,
            **self.details,
        }
