"""Read/write one MinIO/S3 bucket as a medallion layer."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import time
from pathlib import Path

from botocore.exceptions import ClientError

from climate_platform.s3.client import medallion_client

_MISSING_CODES = frozenset({"404", "NoSuchKey", "NotFound"})
_PRECONDITION_CODES = frozenset({"PreconditionFailed", "412"})
_HEAD_UNSUPPORTED_CODES = frozenset({"InvalidArgument", "InvalidRequest", "NotImplemented"})
_MAX_ATTEMPTS = 5


def _error_code(exc):
    return exc.response.get("Error", {}).get("Code")


def _sha256_hex(checksum):
    try:
        return base64.b64decode(checksum).hex()
    except (binascii.Error, TypeError, ValueError):
        return None


class LayerStore:
    def __init__(self, bucket, client=None):
        self.bucket = bucket
        self.client = client or medallion_client()

    def list(self, prefix):
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield item["Key"], item["Size"]

    def download(self, key, destination, *, expected_size=None, expected_sha256=None):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        digest = hashlib.sha256()
        total = 0
        try:
            with response["Body"] as stream, temporary.open("wb") as out:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    total += len(chunk)
                    if expected_size is not None and total > expected_size:
                        raise ValueError("Downloaded object exceeds expected size")
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if total != response["ContentLength"]:
                raise ValueError("Downloaded object size mismatch")
            if expected_size is not None and total != expected_size:
                raise ValueError("Downloaded object size mismatch")
            if expected_sha256 is not None and digest.hexdigest() != expected_sha256:
                raise ValueError("Downloaded object checksum mismatch")
            os.replace(temporary, destination)
            return destination
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def publish(self, path, key, *, content_type="application/octet-stream"):
        """Publish with a checksum-verified conditional PUT and a bounded race retry.

        The server checksum is compared with the local digest; ETag and user metadata are
        only used as concurrency tokens, never as checksum evidence.
        """
        path = Path(path)
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        sha256 = digest.hexdigest()
        checksum = base64.b64encode(bytes.fromhex(sha256)).decode("ascii")
        for attempt in range(_MAX_ATTEMPTS):
            state = self._inspect(key)
            if state is not None and state["sha256"] == sha256 and state["size"] == size:
                return {"key": key, "sha256": sha256, "size_bytes": size, "uploaded": False}
            conditions = {"IfNoneMatch": "*"} if state is None else {"IfMatch": state["etag"]}
            try:
                with path.open("rb") as stream:
                    response = self.client.put_object(
                        Bucket=self.bucket,
                        Key=key,
                        Body=stream,
                        ContentLength=size,
                        ContentType=content_type,
                        ChecksumSHA256=checksum,
                        Metadata={"sha256": sha256},
                        **conditions,
                    )
            except ClientError as exc:
                if _error_code(exc) in _PRECONDITION_CODES:
                    time.sleep(min(0.05 * (2**attempt), 1.0))
                    continue
                raise
            self._verify_put(key, sha256, size, checksum, response)
            return {"key": key, "sha256": sha256, "size_bytes": size, "uploaded": True}
        raise RuntimeError(f"S3 layer object {key!r} kept changing during publish")

    def _head(self, key):
        try:
            return self.client.head_object(Bucket=self.bucket, Key=key, ChecksumMode="ENABLED")
        except ClientError as exc:
            code = _error_code(exc)
            if code in _MISSING_CODES:
                return None
            if code in _HEAD_UNSUPPORTED_CODES:
                return self.client.head_object(Bucket=self.bucket, Key=key)
            raise

    def _inspect(self, key):
        """Return the stored checksum/ETag state, reading the body only when no checksum exists."""
        head = self._head(key)
        if head is None:
            return None
        checksum = _sha256_hex(head.get("ChecksumSHA256"))
        if checksum is not None:
            return {
                "etag": head.get("ETag"),
                "sha256": checksum,
                "size": head.get("ContentLength"),
            }
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        digest = hashlib.sha256()
        size = 0
        with response["Body"] as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return {
            "etag": response.get("ETag", head.get("ETag")),
            "sha256": digest.hexdigest(),
            "size": size,
        }

    def _verify_put(self, key, sha256, size, checksum, response):
        if response.get("ChecksumSHA256") == checksum:
            return
        head = self._head(key)
        if head is None:
            raise ValueError("Published layer object is missing after upload")
        stored = _sha256_hex(head.get("ChecksumSHA256"))
        if stored is not None:
            if stored != sha256 or head.get("ContentLength") != size:
                raise ValueError("Published layer object failed checksum/size verification")
            return
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        digest = hashlib.sha256()
        total = 0
        with response["Body"] as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(chunk)
                digest.update(chunk)
        if total != size or response["ContentLength"] != size or digest.hexdigest() != sha256:
            raise ValueError("Published layer object failed checksum/size verification")

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if _error_code(exc) in _MISSING_CODES:
                return False
            raise
