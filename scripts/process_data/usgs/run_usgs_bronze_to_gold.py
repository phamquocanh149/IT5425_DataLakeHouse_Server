"""Run the USGS medallion automatically once the Bronze crawl is complete (thin entry).

The implementation lives in ``climate_platform.datasets.usgs.runner_cli``; the checkout
``src`` directory is added to ``sys.path`` only so this file can be executed directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from climate_platform.datasets.usgs.runner_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
