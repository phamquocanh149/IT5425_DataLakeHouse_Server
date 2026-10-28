import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.maintenance import migrate_json

if __name__ == "__main__":
    report = migrate_json()
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["errors"] else 0)
