"""Run the existing real HTTP suite from either workspace or Server checkout."""

from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "pytest", "tests/integration", "-q"], cwd=root)
    )
