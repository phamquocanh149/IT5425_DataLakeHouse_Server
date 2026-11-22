"""Publish a verified local Portal release. Source writers must be paused."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.portal.releases import prepare_release, activate, verify_release  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path)
    p.add_argument("--portal-root", type=Path, default=Path("data_lake/portal"))
    p.add_argument("--gis-python", type=Path)
    p.add_argument("--release-id")
    p.add_argument("--activate", action="store_true")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    if a.activate:
        activate(a.portal_root, a.release_id)
    elif a.verify:
        print(
            json.dumps(
                {
                    k: v
                    for k, v in verify_release(a.portal_root, a.release_id).items()
                    if k != "hashes"
                }
            )
        )
    else:
        if not a.source_root or not a.gis_python:
            p.error("--source-root and --gis-python are required")
        result = prepare_release(a.source_root, a.portal_root, a.gis_python, a.release_id)
        print(json.dumps({k: v for k, v in result.items() if k != "hashes"}))


if __name__ == "__main__":
    main()
