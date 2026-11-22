"""Console entry points for the installed package.

Each command is a thin wrapper that reuses the existing operational code paths so the
behaviour stays identical to the original ``scripts/*.py`` invocations.
"""

import argparse
import logging
import sys


def serve():
    """``climate-platform``: run the FastAPI ingestion server with Uvicorn."""
    import uvicorn

    from climate_platform.config import settings

    uvicorn.run(
        "climate_platform.api.app:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
    )


def usdm_replay(argv=None):
    """``climate-usdm-replay``: offline USDM replay into Bronze/Silver/Gold."""
    import json
    from pathlib import Path

    from climate_platform.datasets.usdm.processor import run_pipeline

    parser = argparse.ArgumentParser(
        prog="climate-usdm-replay",
        description="Run offline USDM replay with the Server's configured registry and Bronze backend.",
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--gis-python", required=True, type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args(argv)
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


def usdm_worker():
    """``climate-usdm-worker``: isolated GIS worker (grid preparation / weekly processing)."""
    from climate_platform.datasets.usdm.science import main

    return main()


def verify_usdm(argv=None):
    """``climate-verify-usdm``: cross-check source/output hashes and Gold reference."""
    from scripts.verify_usdm import main

    return main(argv)


def prepare_portal(argv=None):
    """``climate-prepare-portal``: publish a verified local Portal release."""
    from scripts.prepare_portal import main

    return main(argv)
