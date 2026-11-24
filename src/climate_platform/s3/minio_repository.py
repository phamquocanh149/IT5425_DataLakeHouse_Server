"""MinIO/S3 object repository. ETags and user metadata are never checksum evidence.

This repository is the single place that talks to MinIO; the boto3 client itself is built
by the shared factory in ``s3.client`` so the readiness probe reuses the same config.
"""

import base64
import hashlib
from pathlib import Path

from botocore.exceptions import ClientError

from climate_platform.config import settings
from climate_platform.s3.client import s3_client


class S3Storage:
    def __init__(self):
        self.bucket = settings.S3_BUCKET_BRONZE
        self.client = s3_client(signature_version="s3v4")

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
