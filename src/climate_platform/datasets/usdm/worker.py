"""USDM isolated GIS worker invocation.

One job: run the byte-pinned ``science.py`` worker in a separate interpreter and surface its
failure. No science here and no product knowledge.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

WORKER = Path(__file__).with_name("science.py")
DIAGNOSTIC_LIMIT = 64 * 1024


def _store_diagnostics(stderr: bytes) -> str:
    """Persist worker stderr to a private temp file; never embed it in the report/logs.

    The worker's stderr can contain internal absolute paths and tracebacks, so it is kept
    local (mode 0600, non-predictable name) and only referenced by path in the raised error.
    """
    descriptor, name = tempfile.mkstemp(prefix="climate-usdm-worker-", suffix=".stderr.log")
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(stderr[-DIAGNOSTIC_LIMIT:])
    return name


def run_worker(python, args):
    result = subprocess.run(
        [str(python), str(WORKER), *map(str, args)], capture_output=True, timeout=600
    )
    if result.returncode:
        try:
            diagnostic = _store_diagnostics(result.stderr)
        except OSError:
            diagnostic = None
        detail = f"; diagnostics: {diagnostic}" if diagnostic else ""
        raise ValueError(f"GIS worker failed (exit {result.returncode}){detail}")
