"""Run the NLDAS medallion automatically once reference weeks are complete (thin entry).

Implementation lives in ``climate_platform.datasets.nldas.runner_cli``; ``src`` is added to
``sys.path`` only so this file can be executed directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from climate_platform.datasets.nldas.runner_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
