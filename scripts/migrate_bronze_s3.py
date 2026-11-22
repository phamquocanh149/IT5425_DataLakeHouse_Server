"""Run after legacy JSON import. Defaults to inventory/dry-run; use --apply to copy."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.s3_maintenance import local_inventory, migrate_bronze  # noqa: E402

from server.metadata import metadata_manager  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    metadata_manager.initialize()
    result = migrate_bronze(dry_run=not args.apply)
    result["inventory"] = local_inventory()
    print(json.dumps(result, indent=2))
    sys.exit(1 if result["errors"] else 0)
