"""Build NLDAS Gold (thin entry point).

Implementation lives in ``climate_platform.datasets.nldas.cli``; ``src`` is added to
``sys.path`` only so this file can be executed directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from climate_platform.datasets.nldas.cli import gold_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(gold_main())
