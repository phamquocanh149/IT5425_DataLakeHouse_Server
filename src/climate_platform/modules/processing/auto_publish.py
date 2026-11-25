"""Dataset-agnostic auto-publish: sync Bronze from S3, build layers, publish to Silver/Gold.

Per-dataset knowledge lives in a ``SourcePublisher`` adapter under ``datasets/<source>/publish.py``.
This module owns the shared plumbing: registry-record download with checksums, artifact
upload with checksum verification, and the result shape the worker reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Protocol

from climate_platform.common.hashing import file_hash

LAYERS = ("silver", "gold")
MAX_ARCHIVE_MEMBERS = 20_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024


@dataclass
class Artifact:
    layer: str
    path: Path
    key: str


@dataclass
class PublishResult:
    source: str
    ready: bool = False
    reason: str = ""
    bronze_records: int = 0
    bronze_downloaded: int = 0
    bronze_cached: int = 0
    silver_objects: int = 0
    gold_objects: int = 0
    details: dict = field(default_factory=dict)
    failures: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "source": self.source,
            "ready": self.ready,
            "reason": self.reason,
            "bronze_records": self.bronze_records,
            "bronze_downloaded": self.bronze_downloaded,
            "bronze_cached": self.bronze_cached,
            "silver_objects": self.silver_objects,
            "gold_objects": self.gold_objects,
            "details": self.details,
            "failures": self.failures,
        }

    def exit_code(self):
        return 1 if self.failures else 0


class SourcePublisher(Protocol):
    source: str

    def run(
        self, records, *, bronze_store, cache_root, log=print
    ) -> tuple[list[Artifact], PublishResult]: ...


def _content_type(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".parquet":
        return "application/vnd.apache.parquet"
    if suffix in (".json",):
        return "application/json"
    if suffix in (".csv",):
        return "text/csv"
    if suffix in (".geojson",):
        return "application/geo+json"
    return "application/octet-stream"


def safe_record_name(filename):
    """Return the basename for a record upload; reject names that could change a path."""
    name = Path(str(filename or "")).name
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("Invalid record filename")
    return name


def safe_archive_parts(name):
    """Split an archive member into safe POSIX parts.

    Reject Windows drive/UNC/root anchors, backslashes, colons and ``..`` so a member
    cannot escape the extraction root on any platform.
    """
    name = str(name or "")
    if not name or "\x00" in name or "\\" in name:
        raise ValueError("Archive member uses a forbidden name or path separator")
    member = PureWindowsPath(name)
    if member.drive or member.root:
        raise ValueError("Archive member escapes the extraction root")
    parts = tuple(part for part in member.parts if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Archive member escapes the extraction root")
    if any(":" in part for part in parts):
        raise ValueError("Archive member contains a forbidden drive/stream separator")
    return parts


def check_archive_limits(members):
    """Reject an archive that declares too many members or too much uncompressed data."""
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("Archive contains too many members")
    declared = 0
    for member in members:
        declared += max(0, member.file_size)
        if declared > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("Archive expands beyond the configured limit")
    return declared


def extract_member_limited(bundle, member, destination, *, max_bytes):
    """Stream one member to ``destination`` while enforcing a real (not declared) byte cap."""
    destination = Path(destination)
    written = 0
    try:
        with bundle.open(member) as source, destination.open("wb") as output:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError("Archive expands beyond the configured limit")
                output.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return written


def _eligible_record(record, store):
    return bool(
        record.status == "VERIFIED"
        and record.is_current
        and record.s3_object_key
        and record.s3_bucket == store.bucket
    )


def record_order(record):
    """Oldest-to-newest key; ties break on revision and then file id."""
    return (
        str(getattr(record, "received_at", "") or ""),
        int(getattr(record, "revision", 0) or 0),
        str(getattr(record, "file_id", "") or ""),
    )


def record_targets(records, store, target_for):
    """Return the cache targets of every current record, in write order."""
    targets = []
    for record in sorted(
        (record for record in records if _eligible_record(record, store)),
        key=record_order,
    ):
        target = target_for(record)
        if target is not None:
            targets.append(Path(target))
    return targets


def prune_cache(root, keep, *, extra=()):
    """Remove files under ``root`` that no current record owns; markers follow their target.

    ``root`` is a publisher-owned input cache (never an output root), so a file that is not
    an expected target is stale by definition. Empty directories are removed as well.
    """
    root = Path(root)
    if not root.is_dir():
        return 0
    keep_paths = {Path(item).resolve() for item in (*keep, *extra)}
    keep_markers = {Path(str(item) + ".sha256").resolve() for item in keep_paths}
    removed = 0
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            resolved = path.resolve()
            if resolved not in keep_paths and resolved not in keep_markers:
                path.unlink()
                removed += 1
        elif path.is_dir() and path != root:
            try:
                path.rmdir()
            except OSError:
                pass
    return removed


def download_records(records, store, target_for, log=print):
    """Download verified current records under ``store.bucket``; skip unchanged cached files.

    Records are written oldest-to-newest so a target shared by two current records (a stale
    row and its replacement) ends up with the newest bytes, never the older ones.
    """
    downloaded = cached = 0
    ordered = sorted(
        (record for record in records if _eligible_record(record, store)),
        key=record_order,
    )
    for record in ordered:
        target = target_for(record)
        if target is None:
            continue
        target = Path(target)
        marker = target.with_name(target.name + ".sha256")
        if target.is_file() and marker.is_file():
            if marker.read_text(encoding="ascii").strip() == record.sha256:
                cached += 1
                continue
        if target.is_file() and file_hash(target) == record.sha256:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(record.sha256 + "\n", encoding="ascii")
            cached += 1
            continue
        store.download(
            record.s3_object_key,
            target,
            expected_size=record.size_bytes,
            expected_sha256=record.sha256,
        )
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(record.sha256 + "\n", encoding="ascii")
        downloaded += 1
        log(f"[{record.source}] downloaded {record.original_filename}")
    return downloaded, cached


def tree_artifacts(layer, root, key_prefix, *, suffixes=None):
    """Build upload artifacts for every file under ``root`` (keys are ``key_prefix/relpath``)."""
    root = Path(root)
    if not root.is_dir():
        return []
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        relative = path.relative_to(root).as_posix()
        artifacts.append(Artifact(layer=layer, path=path, key=f"{key_prefix}/{relative}"))
    return artifacts


def publish_artifacts(artifacts, stores, log=print):
    counts = {layer: 0 for layer in LAYERS}
    for artifact in artifacts:
        store = stores[artifact.layer]
        result = store.publish(
            artifact.path, artifact.key, content_type=_content_type(artifact.path)
        )
        counts[artifact.layer] += 1
        if result.get("uploaded"):
            log(f"[{artifact.layer}] uploaded {artifact.key}")
    return counts


def publish_source(publisher, records, *, stores, cache_root, log=print):
    """Run one adapter and publish the artifacts it declares."""
    artifacts, result = publisher.run(
        records, bronze_store=stores["bronze"], cache_root=cache_root, log=log
    )
    if not artifacts:
        return result
    try:
        counts = publish_artifacts(artifacts, stores, log)
    except Exception as exc:
        result.failures["publish"] = f"{type(exc).__name__}: {exc}"
        return result
    result.silver_objects = counts["silver"]
    result.gold_objects = counts["gold"]
    return result


def default_publishers(sources=None):
    """Return the enabled source publishers; import adapters lazily to avoid cycles."""
    from climate_platform.datasets.nldas.publish import NldasPublisher
    from climate_platform.datasets.noaa.publish import NoaaPublisher
    from climate_platform.datasets.usdm.publish import UsdmPublisher
    from climate_platform.datasets.usgs.publish import UsgsPublisher

    registry = {
        "nldas": NldasPublisher,
        "noaa": NoaaPublisher,
        "usdm": UsdmPublisher,
        "usgs": UsgsPublisher,
    }
    selected = sources or list(registry)
    return [registry[name]() for name in selected]
