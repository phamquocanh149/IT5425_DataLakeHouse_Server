"""Copy a Portal control snapshot and immutable releases to a new independent root.

Pause release publication and grant changes during backup. Destination must not exist.
Restores deliberately invalidate browser sessions and transient selections.
"""

import argparse
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from climate_platform.api.portal.config import PortalConfig
from climate_platform.api.portal.releases import snapshot, verify_release


def copy_portal(source, destination):
    source = Path(source).resolve()
    destination = PortalConfig(storage_root=destination).storage_root
    if destination.exists() or source in destination.parents or destination in source.parents:
        raise ValueError("Destination must be new and independent of source")
    destination.mkdir(parents=True)
    snapshot(source / "control.sqlite3", destination / "control.sqlite3")
    with closing(sqlite3.connect(destination / "control.sqlite3")) as db, db:
        active = db.execute("SELECT value FROM config WHERE key='active_release'").fetchone()
        if not active:
            raise ValueError("No active release")
        for folder in sorted((source / "releases").iterdir()):
            if not folder.is_dir() or folder.is_symlink():
                raise ValueError("Unexpected release entry")
            verify_release(source, folder.name)
            shutil.copytree(folder, destination / "releases" / folder.name)
            verify_release(destination, folder.name)
        verify_release(destination, active[0])
        for table in ("sessions", "transient", "leases", "usage"):
            db.execute(f"DELETE FROM {table}")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Invalid control snapshot")
    return active[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print("Verified active release:", copy_portal(args.source, args.destination))
