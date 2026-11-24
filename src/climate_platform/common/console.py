"""Console helpers shared by the batch pipeline CLIs.

One job: make stdout/stderr print the workspace's UTF-8 paths safely on legacy consoles.
"""

from __future__ import annotations

import sys


def configure_stdio() -> None:
    """Keep UTF-8 paths printable when stdout/stderr use a legacy encoding."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
