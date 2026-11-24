"""USDM isolated GIS worker invocation.

One job: run the byte-pinned ``science.py`` worker in a separate interpreter and surface its
failure. No science here and no product knowledge.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

WORKER = Path(__file__).with_name("science.py")


def run_worker(python, args):
    result = subprocess.run(
        [str(python), str(WORKER), *map(str, args)], capture_output=True, timeout=600
    )
    if result.returncode:
        # Worker diagnostics retained locally, not emitted as potentially sensitive payload logs.
        raise ValueError(
            "GIS worker failed: " + result.stderr.decode("utf-8", errors="replace")[-3000:]
        )
