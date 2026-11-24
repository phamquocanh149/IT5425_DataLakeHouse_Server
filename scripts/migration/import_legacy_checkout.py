"""Copy verified legacy JSON/raw from a read-only checkout into the active registry volume."""

import argparse
import json
import shutil
import sqlite3
from contextlib import closing
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from climate_platform.common.hashing import file_hash  # noqa: E402
from climate_platform.modules.catalog.maintenance import migrate_json  # noqa: E402
from climate_platform.entity.view import FileMetadata  # noqa: E402
from climate_platform.repositories.catalog_repository import (  # noqa: E402
    metadata_manager,
)
from climate_platform.config import settings  # noqa: E402


def run(root, apply=False):
    root = Path(root).resolve()
    candidates = []
    for path in sorted((root / "metadata").glob("*.json")):
        record = FileMetadata(**json.loads(path.read_text(encoding="utf-8")))
        source = (root / record.stored_path).resolve()
        source.relative_to(root / "data_lake" / "bronze")
        target = metadata_manager.resolve_raw(record.stored_path)
        if file_hash(source) != record.sha256 or source.stat().st_size != record.size_bytes:
            raise ValueError("Legacy checksum mismatch")
        if target.exists() and file_hash(target) != record.sha256:
            raise ValueError("Destination conflict")
        candidates.append((path, source, target))
    print(json.dumps({"apply": apply, "files": [p.name for p, _, _ in candidates]}))
    if not apply:
        return
    metadata_manager.initialize()
    backup = metadata_manager.metadata_dir / "backups" / ("before-import-" + uuid.uuid4().hex)
    backup.mkdir(parents=True)
    with (
        metadata_manager.connection() as db,
        closing(sqlite3.connect(backup / "ingestion.sqlite3")) as dest,
    ):
        db.backup(dest)
    for path, source, target in candidates:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with source.open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
        metadata_target = settings.metadata_path / ("imported-" + path.name)
        if metadata_target.exists():
            if metadata_target.read_bytes() != path.read_bytes():
                raise ValueError("Existing metadata conflict")
        else:
            with metadata_target.open("xb") as dst:
                dst.write(path.read_bytes())
    result = migrate_json()
    print(json.dumps(result, indent=2))
    if result["errors"]:
        raise RuntimeError("Legacy import requires review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(args.source, args.apply)
