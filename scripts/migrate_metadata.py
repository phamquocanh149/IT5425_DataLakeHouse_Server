import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.maintenance import migrate_json

from server.metadata import metadata_manager  # noqa: E402

if __name__ == "__main__":
    metadata_manager.initialize()
    report = migrate_json()
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["errors"] else 0)
