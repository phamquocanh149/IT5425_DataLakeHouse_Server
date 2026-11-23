import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from climate_platform.catalog.maintenance import reconcile  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report inconsistencies; never delete raw files")
    parser.add_argument("--checksum", action="store_true")
    parser.add_argument(
        "--repair-status",
        action="store_true",
        help="Update registry status only after validating disk contents",
    )
    args = parser.parse_args()
    report = reconcile(checksum=args.checksum, repair=args.repair_status)
    print(json.dumps(report, indent=2))
    sys.exit(
        1
        if any(
            report.get(k)
            for k in [
                "missing",
                "corrupt",
                "unsafe_paths",
                "orphan_files",
                "temporary_files",
                "orphan_objects",
                "unmigrated",
            ]
        )
        else 0
    )
