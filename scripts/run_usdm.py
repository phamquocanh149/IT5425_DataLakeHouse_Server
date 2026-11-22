"""Run offline USDM replay with the Server's configured registry and Bronze backend."""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.usdm import run_pipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--gis-python", required=True, type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    try:
        report = run_pipeline(
            args.source_root, args.output_root, args.gis_python, args.start_date, args.end_date
        )
    except Exception as exc:
        logging.error("USDM pipeline could not run: %s", type(exc).__name__)
        return 1
    print(json.dumps({key: value for key, value in report.items() if key != "weeks"}))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
