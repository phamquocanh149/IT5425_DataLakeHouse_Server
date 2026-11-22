"""Offline S3 backup bundles. Stop ALL writers and MinIO before create/restore.

Run in an isolated helper with explicit mounts, never inside the live API process.
Checksums detect corruption, not malicious replacement; protect backup storage.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tarfile
import tempfile


ARCHIVES = {"registry": "registry.tar.gz", "minio": "minio-data.tar.gz", "legacy": "legacy.tar.gz"}
DATABASES = ("ingestion.sqlite3", "access.sqlite3")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def distinct_paths(paths):
    resolved = [Path(p).resolve() for p in paths]
    for i, path in enumerate(resolved):
        for other in resolved[i + 1 :]:
            if path == other or path in other.parents or other in path.parents:
                raise ValueError("Backup and storage paths must be distinct and non-nested")


def create(bundle, registry, minio, legacy, *, project, images):
    distinct_paths([bundle, registry, minio, legacy])
    if not (minio / ".minio.sys").is_dir():
        raise ValueError("Expected full stopped MinIO data volume, including .minio.sys")
    if not all((registry / name).is_file() for name in DATABASES) or not legacy.is_dir():
        raise ValueError("Registry databases and legacy/temp volume are required")
    bundle.mkdir(parents=True, exist_ok=False)
    checkpoint = utc_now()
    with tempfile.TemporaryDirectory() as directory:
        snapshots = Path(directory)
        for name in DATABASES:
            with closing(
                sqlite3.connect((registry / name).resolve().as_uri() + "?mode=ro", uri=True)
            ) as src:
                with closing(sqlite3.connect(snapshots / name)) as dst:
                    src.backup(dst)
                    if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite backup integrity check failed")
        with closing(sqlite3.connect(snapshots / "ingestion.sqlite3")) as db:
            db.row_factory = sqlite3.Row
            inventory = [
                dict(row)
                for row in db.execute(
                    "SELECT file_id, source, source_date, dataset_key, revision, sha256, size_bytes, "
                    "status, stored_path, s3_bucket, s3_object_key, s3_version_id "
                    "FROM observations ORDER BY file_id"
                )
            ]
            schema_version = db.execute("PRAGMA user_version").fetchone()[0]
        omitted = {
            name + suffix for name in DATABASES for suffix in ("", "-wal", "-shm", "-journal")
        }
        with tarfile.open(bundle / ARCHIVES["registry"], "w:gz") as archive:
            for path in registry.iterdir():
                if path.name not in omitted:
                    archive.add(path, arcname=path.name)
            for name in DATABASES:
                archive.add(snapshots / name, arcname=name)
        for kind, source in (("minio", minio), ("legacy", legacy)):
            with tarfile.open(bundle / ARCHIVES[kind], "w:gz") as archive:
                archive.add(source, arcname=".")
    manifest = {
        "format_version": 1,
        "backend": "s3",
        "project": project,
        "checkpoint_utc": checkpoint,
        "completed_utc": utc_now(),
        "method": "all writers paused; full stopped MinIO volume; SQLite Connection.backup",
        "images": images,
        "schema_version": schema_version,
        "observations": inventory,
        "artifacts": {
            kind: {
                "file": name,
                "bytes": (bundle / name).stat().st_size,
                "sha256": sha256(bundle / name),
            }
            for kind, name in ARCHIVES.items()
        },
    }
    target = bundle / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle / "manifest.sha256").write_text(sha256(target) + "\n", encoding="ascii")
    verify(bundle)
    return manifest


def verify(bundle):
    target = bundle / "manifest.json"
    if sha256(target) != (bundle / "manifest.sha256").read_text(encoding="ascii").strip():
        raise ValueError("Manifest checksum mismatch")
    manifest = json.loads(target.read_text(encoding="utf-8"))
    if manifest["format_version"] != 1 or manifest["backend"] != "s3":
        raise ValueError("Unsupported backup format/backend")
    if set(manifest["artifacts"]) != set(ARCHIVES):
        raise ValueError("Incomplete storage bundle")
    for kind, name in ARCHIVES.items():
        item = manifest["artifacts"][kind]
        path = bundle / name
        if (
            item["file"] != name
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError("Artifact checksum/size mismatch: " + kind)
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                relative = Path(member.name)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or "\\" in member.name
                    or ":" in member.name
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("Unsafe archive member")
    return manifest


def restore(bundle, registry, minio, legacy):
    distinct_paths([bundle, registry, minio, legacy])
    manifest = verify(bundle)  # Verify ALL archives before touching destination volumes.
    targets = {"registry": registry, "minio": minio, "legacy": legacy}
    for path in targets.values():
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError("Restore requires empty NEW volumes: " + str(path))
    for kind, path in targets.items():
        path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(bundle / ARCHIVES[kind], "r:gz") as archive:
            # Avoid extractall and its platform-dependent link/path behavior.
            directories = []
            for member in archive.getmembers():
                destination = path / member.name
                destination.resolve().relative_to(path.resolve())
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    directories.append((destination, member))
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as src, destination.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
                    archive.chmod(member, destination)
                    archive.chown(member, destination, numeric_owner=True)
            for destination, member in reversed(directories):
                archive.chmod(member, destination)
                archive.chown(member, destination, numeric_owner=True)
    for name in DATABASES:
        with closing(
            sqlite3.connect((registry / name).resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Restored SQLite integrity check failed")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["create", "verify", "restore"])
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--minio", type=Path)
    parser.add_argument("--legacy", type=Path)
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--image", action="append", default=[])
    args = parser.parse_args()
    if args.operation == "verify":
        manifest = verify(args.bundle)
    else:
        if not args.writers_stopped or not all((args.registry, args.minio, args.legacy)):
            parser.error(
                "Stop all writers/MinIO; supply --writers-stopped and all three volume paths"
            )
        if args.operation == "create":
            if not args.project or not args.image:
                parser.error("create requires --project and resolved --image references")
            manifest = create(
                args.bundle,
                args.registry,
                args.minio,
                args.legacy,
                project=args.project,
                images=args.image,
            )
        else:
            manifest = restore(args.bundle, args.registry, args.minio, args.legacy)
    print(
        json.dumps(
            {
                "operation": args.operation,
                "checkpoint_utc": manifest["checkpoint_utc"],
                "observations": len(manifest["observations"]),
                "status": "ok",
            }
        )
    )


if __name__ == "__main__":
    main()
