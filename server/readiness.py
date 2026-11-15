"""Bounded dependency probes. Never initialize or silently recreate a missing registry."""

import json
import logging
import sqlite3
import threading
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import settings
from .access import access_probe
from .metadata import metadata_manager

logger = logging.getLogger(__name__)


def s3_probe_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(
            connect_timeout=settings.READINESS_TIMEOUT_SECONDS,
            read_timeout=settings.READINESS_TIMEOUT_SECONDS,
            retries={"total_max_attempts": 1},
            s3={"addressing_style": "path"},
        ),
    )


def sqlite_probe():
    db = sqlite3.connect(
        metadata_manager.db_path.resolve().as_uri() + "?mode=rw",
        uri=True,
        timeout=settings.READINESS_TIMEOUT_SECONDS,
    )
    try:
        db.execute("SELECT 1").fetchone()
        db.execute("SELECT file_id FROM observations LIMIT 1").fetchone()
        # Detect a writer lock/read-only volume without changing persisted data.
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE observations SET file_id=file_id WHERE 0")
        db.rollback()
    finally:
        db.close()


def validate_storage():
    sqlite_probe()
    access_probe()
    if settings.STORAGE_BACKEND != "s3":
        return
    with s3_probe_client() as client:
        bucket = settings.S3_BUCKET_BRONZE
        client.head_bucket(Bucket=bucket)
        client.list_objects_v2(Bucket=bucket, MaxKeys=1)
        if client.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
            raise RuntimeError("Bronze bucket versioning must be Enabled")
        try:
            policy = json.loads(client.get_bucket_policy(Bucket=bucket)["Policy"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchBucketPolicy":
                raise
        else:
            # Private Bronze needs no resource Allow policy. Fail closed for conditional
            # or complex principals too; IAM grants the dedicated ingestion identity.
            if any(s.get("Effect") == "Allow" for s in policy.get("Statement", [])):
                raise RuntimeError("Bronze bucket must not have a resource Allow policy")
        if settings.REQUIRE_SSE_KMS:
            rules = client.get_bucket_encryption(Bucket=bucket)[
                "ServerSideEncryptionConfiguration"
            ]["Rules"]
            if not rules or any(
                r.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") != "aws:kms"
                for r in rules
            ):
                raise RuntimeError("Bronze requires default SSE-KMS")
        if settings.REQUIRE_OBJECT_LOCK:
            config = client.get_object_lock_configuration(Bucket=bucket)["ObjectLockConfiguration"]
            if config.get("ObjectLockEnabled") != "Enabled" or not config.get("Rule", {}).get(
                "DefaultRetention"
            ):
                raise RuntimeError("Bronze requires Object Lock with default retention")


class Readiness:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.expires = 0
        self.ok = False

    def check(self):
        with self.lock:
            if time.monotonic() < self.expires:
                return self.ok
            try:
                sqlite_probe()
                access_probe()
                if settings.STORAGE_BACKEND == "s3":
                    with s3_probe_client() as client:
                        client.head_bucket(Bucket=settings.S3_BUCKET_BRONZE)
                self.ok = True
            except Exception as exc:
                logger.warning("Readiness dependency failed: %s", type(exc).__name__)
                self.ok = False
            self.expires = time.monotonic() + settings.READINESS_CACHE_SECONDS
            return self.ok


readiness = Readiness()
