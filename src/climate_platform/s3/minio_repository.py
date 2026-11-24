"""MinIO/S3 object repository. ETags and user metadata are never checksum evidence.

The boto3 client lives here: the repository is the single place that talks to MinIO,
so there is no separate driver layer.
"""

import base64
import hashlib
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from climate_platform.config import settings


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

    def get_object(self, **kwargs):
        return self.client.get_object(**kwargs)

    def objects(self):
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            yield from page.get("Contents", [])
