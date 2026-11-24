"""Medallion run orchestration shared by every dataset.

One job: take a planned ``RunReport`` and an ordered mapping of stage builders, hold the
exclusive lock, run each planned stage once, and record built/failed outcomes. It owns no
science, no gate logic and no paths — datasets supply those.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Mapping, Sequence

from climate_platform.medallion.lock import exclusive_run

__all__ = ["MedallionRunner", "medallion_lock"]


@contextmanager
def medallion_lock(lock_path, message: str):
    """Exclusive lock that reports contention as a friendly ``RuntimeError``."""
    manager = exclusive_run(lock_path)
    try:
        manager.__enter__()
    except OSError as exc:  # held by another process (BlockingIOError on POSIX)
        raise RuntimeError(message) from exc
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


class MedallionRunner:
    """Run ordered stages under one lock, skipping stages the plan marked unplanned."""

    def __init__(
        self,
        *,
        lock_path,
        order: Sequence[str],
        log: Callable[[str], None],
        lock_message: str,
        stop_on_failure: bool = False,
    ):
        self.lock_path = Path(lock_path)
        self.order = tuple(order)
        self.log = log
        self.lock_message = lock_message
        self.stop_on_failure = stop_on_failure

    def run(self, report, steps: Mapping[str, Callable[[], object]]) -> object:
        """Execute ``steps`` for every stage the report planned, updating it in place."""
        if not report.ready or report.dry_run:
            return report
        with medallion_lock(self.lock_path, self.lock_message):
            for name in self.order:
                if not report.planned.get(name):
                    continue
                try:
                    artifact = steps[name]()
                except Exception as exc:
                    report.failures[name] = f"{type(exc).__name__}: {exc}"
                    self.log(f"[{name}] FAILED: {report.failures[name]}")
                    if self.stop_on_failure:
                        break
                    continue
                report.built[name] = True
                if artifact is not None:
                    report.details.setdefault("artifacts", {})[name] = str(artifact)
                self.log(f"[{name}] {artifact if artifact is not None else 'ok'}")
        return report
