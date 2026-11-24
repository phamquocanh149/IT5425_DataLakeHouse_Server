"""Bounded reader: run the isolated reader worker and map its exit codes to PortalError."""

import json
import subprocess
import sys
from pathlib import Path

from climate_platform.modules.portal.errors import PortalError


def bounded_read(job, timeout=5):
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("read_worker.py"))],
            input=json.dumps(job).encode(),
            capture_output=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except subprocess.TimeoutExpired:
        raise PortalError(503, "READ_TIMEOUT") from None
    if result.returncode == 3:
        raise PortalError(413, "PREVIEW_TOO_LARGE")
    if result.returncode:
        raise PortalError(503, "READER_UNAVAILABLE")
    return json.loads(result.stdout)
