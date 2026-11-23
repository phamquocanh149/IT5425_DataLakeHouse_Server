import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from climate_platform.catalog.maintenance import migrate_json  # noqa: E402
from climate_platform.catalog.repository import metadata_manager  # noqa: E402

if __name__ == "__main__":
    metadata_manager.initialize()
    report = migrate_json()
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["errors"] else 0)
