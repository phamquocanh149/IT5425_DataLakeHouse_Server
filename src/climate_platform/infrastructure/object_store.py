"""Immutable S3 Bronze objects. ETags and user metadata are never checksum evidence."""

import base64
import hashlib
import re
from datetime import date
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from climate_platform.config import settings


def object_key(source, source_date, dataset_key, revision, sha256, filename):
    if source not in settings.ALLOWED_SOURCES:
        raise ValueError("Unsupported source")
    day = date.fromisoformat(source_date)
    if day.isoformat() != source_date or revision < 1 or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Invalid object identity")
    if not dataset_key.strip() or len(dataset_key) > 512 or any(ord(c) < 32 for c in dataset_key):
        raise ValueError("Invalid dataset key")
    # Full hash is collision resistant and encodes even Unicode/path-like dataset IDs safely.
    dataset = hashlib.sha256(dataset_key.encode("utf-8")).hexdigest()
    suffix = Path(filename).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,16}", suffix):
        suffix = ".bin"
    return (
        f"source={source}/year={day.year:04d}/date={source_date}/dataset={dataset}/"
        f"revision={revision}/sha256={sha256}/raw{suffix}"
    )


class S3Storage:
    def __init__(self):
        self.bucket = settings.S3_BUCKET_BRONZE
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(
                signature_version="s3v4",
                connect_timeout=3,
                read_timeout=10,
                retries={"mode": "standard", "total_max_attempts": 3},
                s3={"addressing_style": "path"},
            ),
        )

    def verify(self, key, sha256, size, bucket=None):
        response = self.client.get_object(Bucket=bucket or self.bucket, Key=key)
        digest = hashlib.sha256()
        count = 0
        with response["Body"] as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                count += len(chunk)
                if count > size:
                    raise ValueError("S3 object size mismatch")
                digest.update(chunk)
        if count != size or response["ContentLength"] != size or digest.hexdigest() != sha256:
            raise ValueError("S3 object checksum/size mismatch")
        return response.get("VersionId")

    def publish(self, path, key, sha256, size):
        # Conditional PUT makes retries and concurrent writers incapable of overwriting raw.
        try:
            with Path(path).open("rb") as stream:
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=stream,
                    ContentLength=size,
                    IfNoneMatch="*",
                    ChecksumSHA256=base64.b64encode(bytes.fromhex(sha256)).decode(),
                    Metadata={"sha256": sha256},
                    ContentType="application/octet-stream",
                )
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
                raise
        # Also verifies orphan adoption after a successful PUT followed by failed DB commit.
        return self.verify(key, sha256, size)

    def objects(self):
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            yield from page.get("Contents", [])
