"""Auto-publish worker: for every enabled source, sync Bronze and publish Silver/Gold to S3."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from pathlib import Path

from climate_platform.config import settings
from climate_platform.modules.processing.auto_publish import (
    PublishResult,
    default_publishers,
    publish_source,
)
from climate_platform.repositories.catalog_repository import metadata_manager
from climate_platform.s3.layers import LayerStore

SOURCES = ("nldas", "noaa", "usdm", "usgs")


def _resolve_sources(value):
    if value == "all":
        return list(SOURCES)
    if value not in SOURCES:
        raise SystemExit(f"Unknown source: {value}")
    return [value]


def run_cycle(*, sources=SOURCES, cache_root=None, log=print):
    metadata_manager.initialize_once()
    root = Path(
        cache_root
        or os.environ.get("MEDALLION_PUBLISH_CACHE_ROOT")
        or settings.scratch_path / "medallion-publish"
    )
    stores = {
        "bronze": LayerStore(settings.S3_BUCKET_BRONZE),
        "silver": LayerStore(settings.S3_BUCKET_SILVER),
        "gold": LayerStore(settings.S3_BUCKET_GOLD),
    }
    records = metadata_manager.list_all(read_only=True)
    results = []
    for publisher in default_publishers(sources):
        try:
            result = publish_source(
                publisher,
                records,
                stores=stores,
                cache_root=root / publisher.source,
                log=log,
            )
        except Exception as exc:
            result = PublishResult(
                source=publisher.source,
                failures={"worker": f"{type(exc).__name__}: {exc}"},
            )
        results.append(result.as_dict())
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one cycle")
    mode.add_argument("--watch", action="store_true", help="Poll continuously")
    parser.add_argument("--source", choices=("all", *SOURCES), default="all")
    parser.add_argument("--interval", type=float, default=60, help="Polling interval in seconds")
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args(argv)
    if args.interval < 5:
        parser.error("--interval must be at least 5 seconds")
    sources = _resolve_sources(args.source)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    def log(message):
        print(message, file=sys.stderr, flush=True)

    exit_code = 0
    while not stop.is_set():
        try:
            results = run_cycle(sources=sources, cache_root=args.cache_root, log=log)
            print(json.dumps({"results": results}, sort_keys=True), flush=True)
            exit_code = 1 if any(item["failures"] for item in results) else 0
        except Exception as exc:
            print(json.dumps({"error": type(exc).__name__}), file=sys.stderr, flush=True)
            exit_code = 1
        if args.once or not args.watch:
            return exit_code
        stop.wait(args.interval)
    return exit_code
