"""Stage 5 offline checkpoint. Pause every writer; stop MinIO before copying its volume.

No source deletion, overwrite, automatic service stop, or claim of off-host durability.
The complete manifest is written last. Hashes detect damage, not malicious replacement.
"""

import argparse
from contextlib import closing, contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.storage_backup import distinct_paths, sha256  # noqa: E402


def now():
    return datetime.now(timezone.utc).isoformat()


def safe(root, relative):
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe relative path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe relative path")
    target = root / path
    target.resolve().relative_to(root.resolve())
    return target


def files(root):
    if root.is_symlink():
        raise ValueError("Linked checkpoint root")
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Links are not allowed in checkpoints")
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise ValueError("Hard links are not allowed in checkpoints")
            yield path
        elif not path.is_dir():
            raise ValueError("Special file in checkpoint")


def copy_tree(source, target, omit=()):
    if source.is_symlink():
        raise ValueError("Linked source root")
    target.mkdir(parents=True, exist_ok=False)
    for path in files(source):
        relative = path.relative_to(source)
        if relative.as_posix() in omit:
            continue
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = sha256(path)
        shutil.copyfile(path, dest)
        if sha256(dest) != before or sha256(path) != before:
            raise ValueError("Source changed during checkpoint")
        shutil.copystat(path, dest)
        if os.name != "nt" and os.geteuid() == 0:
            os.chown(dest, path.stat().st_uid, path.stat().st_gid)
    # MinIO needs empty directories too, including .minio.sys.
    for path in source.rglob("*"):
        if path.is_dir():
            (target / path.relative_to(source)).mkdir(parents=True, exist_ok=True)
    for path in sorted(source.rglob("*"), reverse=True):
        if path.is_dir():
            dest = target / path.relative_to(source)
            shutil.copystat(path, dest)
            if os.name != "nt" and os.geteuid() == 0:
                os.chown(dest, path.stat().st_uid, path.stat().st_gid)
    shutil.copystat(source, target)
    if os.name != "nt" and os.geteuid() == 0:
        os.chown(target, source.stat().st_uid, source.stat().st_gid)


def connect(path):
    return closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True))


def snapshot(source, target):
    if source.is_symlink():
        raise ValueError("Linked SQLite source")
    target.parent.mkdir(parents=True, exist_ok=True)
    with connect(source) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity failure")
    shutil.copystat(source, target)
    if os.name != "nt" and os.geteuid() == 0:
        os.chown(target, source.stat().st_uid, source.stat().st_gid)


def object_digest(client, bucket, key, version):
    args = {"Bucket": bucket, "Key": key}
    if version:
        args["VersionId"] = version
    response = client.get_object(**args)
    digest, size = hashlib.sha256(), 0
    with response["Body"] as body:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def s3_inventory(client):
    """Capture all bucket versions/delete markers while writers are stopped."""
    buckets = {}
    for bucket in sorted(b["Name"] for b in client.list_buckets()["Buckets"]):
        versions = []
        for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket):
            for kind in ("Versions", "DeleteMarkers"):
                for obj in page.get(kind, []):
                    item = {
                        "key": obj["Key"],
                        "version": obj["VersionId"],
                        "latest": obj["IsLatest"],
                        "delete_marker": kind == "DeleteMarkers",
                    }
                    if not item["delete_marker"]:
                        item["sha256"], item["bytes"] = object_digest(
                            client, bucket, obj["Key"], obj["VersionId"]
                        )
                    versions.append(item)
        buckets[bucket] = {
            "versioning": client.get_bucket_versioning(Bucket=bucket).get("Status"),
            "versions": sorted(versions, key=lambda item: (item["key"], item["version"])),
        }
    return buckets


def validate_s3_snapshot(root):
    snapshot = json.loads((root / "s3-inventory.json").read_text(encoding="utf-8"))
    with connect(root / "metadata/ingestion.sqlite3") as db:
        for bucket, key, version, digest, size in db.execute(
            "SELECT s3_bucket,s3_object_key,s3_version_id,sha256,size_bytes FROM observations WHERE s3_object_key IS NOT NULL"
        ):
            versions = snapshot[bucket]["versions"]
            matches = [
                v
                for v in versions
                if v["key"] == key and (v["version"] == version if version else v["latest"])
            ]
            if (
                len(matches) != 1
                or matches[0]["delete_marker"]
                or (matches[0]["sha256"], matches[0]["bytes"]) != (digest, size)
            ):
                raise ValueError("S3 version inventory/registry mismatch")
    return snapshot


@contextmanager
def pipeline_lock(root):
    # Same OS lock as server.usdm, without importing API settings/credentials.
    with (root / "pipeline.lock").open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def reconcile(root, *, s3_client=None):
    """Verify every historical build, not just the current serving selection."""
    with connect(root / "metadata/ingestion.sqlite3") as registry:
        registry.row_factory = sqlite3.Row
        observations = {
            r["file_id"]: dict(r) for r in registry.execute("SELECT * FROM observations")
        }
        if registry.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Registry integrity failure")
    pending = 0
    for record in observations.values():
        if record["status"] != "VERIFIED":
            raise ValueError("Reconcile non-VERIFIED observations before checkpoint")
        if record["s3_object_key"]:
            if s3_client is None:
                pending += 1
                continue
            actual, size = object_digest(
                s3_client, record["s3_bucket"], record["s3_object_key"], record["s3_version_id"]
            )
        else:
            raw = safe(root, record["stored_path"])
            actual, size = sha256(raw), raw.stat().st_size
        if (actual, size) != (record["sha256"], record["size_bytes"]):
            raise ValueError("Bronze integrity failure")
    recipes = set()
    total_rows = 0
    with connect(root / "products/warehouse.sqlite3") as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Warehouse integrity failure")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Warehouse foreign key failure")
        builds = db.execute(
            "SELECT build_id,file_id,revision,raw_sha256,manifest,source_date FROM builds"
        ).fetchall()
        for build, file_id, revision, raw_hash, value, source_date in builds:
            manifest = json.loads(value)
            observation = observations.get(file_id)
            if not observation or (revision, raw_hash) != (
                observation["revision"],
                observation["sha256"],
            ):
                raise ValueError("Build/registry lineage mismatch")
            if (
                manifest["file_id"] != file_id
                or manifest["raw_sha256"] != raw_hash
                or manifest["revision"] != revision
                or source_date != observation["source_date"]
                or manifest["source_date"] != source_date
            ):
                raise ValueError("Manifest lineage mismatch")
            identity = {key: manifest[key] for key in ("file_id", "raw_sha256", "recipe")}
            if hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest() != build:
                raise ValueError("Build identity mismatch")
            if set(manifest["products"]) != {"silver", "gold", "quality", "reference"}:
                raise ValueError("Incomplete product manifest")
            for product in manifest["products"].values():
                if sha256(safe(root / "products", product["path"])) != product["sha256"]:
                    raise ValueError("Product checksum mismatch")
            for key in ("cleaner", "worker"):
                digest = manifest["recipe"][key]
                if sha256(safe(root / "recipes", digest + ".py")) != digest:
                    raise ValueError("Recipe checksum mismatch")
                recipes.add(digest)
            reference = manifest["products"]["reference"]
            if reference["sha256"] != manifest["recipe"]["grid"]:
                raise ValueError("Reference grid mismatch")
            # Compare full CSV and warehouse rows, including history; bounded-memory iterator.
            gold = safe(root / "products", manifest["products"]["gold"]["path"])
            count = 0
            seen = set()
            with gold.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    if row["time"] != source_date.replace("-", ""):
                        raise ValueError("Gold time/observation mismatch")
                    if row["grid"] in seen:
                        raise ValueError("Duplicate grid in Gold CSV")
                    seen.add(row["grid"])
                    actual = db.execute(
                        "SELECT time,lon,lat,drought FROM gold_cells WHERE build_id=? AND grid=?",
                        (build, row["grid"]),
                    ).fetchone()
                    if actual != (
                        row["time"],
                        float(row["lon"]),
                        float(row["lat"]),
                        row["drought"],
                    ):
                        raise ValueError("Gold CSV/warehouse mismatch")
                    count += 1
            if (
                db.execute("SELECT count(*) FROM gold_cells WHERE build_id=?", (build,)).fetchone()[
                    0
                ]
                != count
            ):
                raise ValueError("Extra warehouse rows")
            total_rows += count
    access = root / "metadata/access.sqlite3"
    if access.exists():
        with connect(access) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Accounting integrity failure")
    if (root / "s3-inventory.json").exists():
        expected = validate_s3_snapshot(root)
        if s3_client is not None and s3_inventory(s3_client) != expected:
            raise ValueError("Restored S3 versions/delete markers mismatch")
    return {
        "observations": len(observations),
        "builds": len(builds),
        "gold_rows": total_rows,
        "recipe_files": len(recipes),
        "s3_objects_pending_live_verification": pending,
    }


def inventory(root):
    return {
        p.relative_to(root).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size}
        for p in files(root)
    }


def create(
    source,
    bundle,
    *,
    recipes=(),
    minio=None,
    images=(),
    writers_stopped=False,
    version_inventory=None,
):
    if not writers_stopped:
        raise ValueError("Stop all writers and MinIO; explicit acknowledgement required")
    distinct_paths([source, bundle] + ([minio] if minio else []))
    if not images:
        raise ValueError("Record exact release image references")
    if minio and not (minio / ".minio.sys").is_dir():
        raise ValueError("Full stopped MinIO volume required")
    if minio and not version_inventory:
        raise ValueError("Capture all S3 versions before stopping MinIO")
    # Taking the pipeline lock prevents an accidental concurrent USDM runner.
    started = now()
    bundle.mkdir(parents=True, exist_ok=False)
    payload = bundle / "payload"
    payload.mkdir()
    with pipeline_lock(source / "products"):
        for name in ("ingestion.sqlite3", "access.sqlite3"):
            path = source / "metadata" / name
            if name == "access.sqlite3" and not path.exists():
                if minio:
                    raise ValueError("S3 deployment accounting database missing")
                continue  # Offline local replay may never initialize HTTP accounting.
            snapshot(path, payload / "metadata" / name)
        omit = {"warehouse.sqlite3" + suffix for suffix in ("", "-wal", "-shm", "-journal")}
        copy_tree(source / "products", payload / "products", omit=omit | {"pipeline.lock"})
        snapshot(source / "products/warehouse.sqlite3", payload / "products/warehouse.sqlite3")
        bronze = source / "data_lake/bronze"
        if bronze.exists():
            copy_tree(bronze, payload / "data_lake/bronze")
        if minio:
            copy_tree(minio, payload / "minio")
            shutil.copyfile(version_inventory, payload / "s3-inventory.json")
        recipe_root = payload / "recipes"
        recipe_root.mkdir()
        candidates = list(recipes)
        for archive in (source / "products/recipes", source / "recipes"):
            if archive.is_dir():
                candidates.extend(files(archive))
        for path in candidates:
            if path.is_symlink() or not path.is_file():
                raise ValueError("Recipe must be a regular file")
            destination = recipe_root / (sha256(path) + ".py")
            if not destination.exists():
                shutil.copyfile(path, destination)
        result = reconcile(payload)
        if result["s3_objects_pending_live_verification"] and not minio:
            raise ValueError("S3 observations require the stopped MinIO volume")
    manifest = {
        "format_version": 1,
        "checkpoint_utc": started,
        "completed_utc": now(),
        "images": list(images),
        "backend": "s3" if minio else "local",
        "method": "all writers stopped; pipeline lock; SQLite backup API",
        "reconciliation": result,
        "files": inventory(payload),
    }
    temporary = bundle / "manifest.tmp"
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, bundle / "manifest.json")
    (bundle / "manifest.sha256").write_text(sha256(bundle / "manifest.json"), encoding="ascii")
    verify(bundle)
    return manifest


def verify(bundle):
    target = bundle / "manifest.json"
    if sha256(target) != (bundle / "manifest.sha256").read_text(encoding="ascii").strip():
        raise ValueError("Manifest checksum mismatch")
    manifest = json.loads(target.read_text(encoding="utf-8"))
    if manifest["format_version"] != 1 or manifest["backend"] not in {"local", "s3"}:
        raise ValueError("Unsupported checkpoint")
    if inventory(bundle / "payload") != manifest["files"]:
        raise ValueError("Checkpoint file inventory/checksum mismatch")
    result = reconcile(bundle / "payload")
    if result != manifest["reconciliation"]:
        raise ValueError("Checkpoint reconciliation mismatch")
    if manifest["backend"] == "s3" and not (bundle / "payload/minio/.minio.sys").is_dir():
        raise ValueError("Missing full MinIO volume")
    return manifest


def restore(bundle, target):
    distinct_paths([bundle, target])
    manifest = verify(bundle)  # All checks before creating a restore target.
    if target.exists():
        raise ValueError("Restore requires a NEW destination")
    copy_tree(bundle / "payload", target)
    if inventory(target) != manifest["files"]:
        raise ValueError("Restore copy verification failed")
    return reconcile(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=["create", "verify", "restore", "reconcile", "capture-s3"]
    )
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--minio", type=Path)
    parser.add_argument("--recipe", type=Path, action="append", default=[])
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument("--live-s3", action="store_true")
    parser.add_argument("--s3-inventory", type=Path)
    args = parser.parse_args()
    if args.operation == "capture-s3":
        if not args.writers_stopped or not args.s3_inventory:
            parser.error("Pause writers; supply --writers-stopped and NEW --s3-inventory path")
        with closing(backup_s3_client()) as client:
            result = s3_inventory(client)
        with args.s3_inventory.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps({"captured_buckets": len(result), "status": "ok"}))
        return
    if args.operation != "reconcile" and not args.bundle:
        parser.error("--bundle is required")
    if args.operation != "verify" and not args.root:
        parser.error("--root is required")
    if args.operation == "create":
        result = create(
            args.root,
            args.bundle,
            recipes=args.recipe,
            minio=args.minio,
            images=args.image,
            writers_stopped=args.writers_stopped,
            version_inventory=args.s3_inventory,
        )
    elif args.operation == "verify":
        result = verify(args.bundle)
    elif args.operation == "restore":
        result = restore(args.bundle, args.root)
    elif args.live_s3:
        with closing(backup_s3_client()) as client:
            result = reconcile(args.root, s3_client=client)
    else:
        result = reconcile(args.root)
    print(json.dumps(result, indent=2))


def backup_s3_client():
    # Separate backup identity via AWS credential chain; never default to API credentials.
    import boto3
    from botocore.config import Config

    endpoint = os.environ.get("S3_BACKUP_ENDPOINT")
    if not endpoint:
        raise ValueError("Set explicit S3_BACKUP_ENDPOINT for the intended instance")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        config=Config(connect_timeout=5, read_timeout=30, retries={"total_max_attempts": 3}),
    )


if __name__ == "__main__":
    main()
