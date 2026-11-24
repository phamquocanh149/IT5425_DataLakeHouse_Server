"""Bounded dependency probes. Never initialize or silently recreate a missing registry."""

import json
import logging
import threading
import time
from contextlib import closing

from botocore.exceptions import ClientError
from sqlalchemy import false, literal, select, update

from climate_platform.config import settings
from climate_platform.entity.registry import Observation
from climate_platform.repositories.access_repository import access_probe
from climate_platform.repositories.catalog_repository import metadata_manager
from climate_platform.repositories.database import connection
from climate_platform.s3.client import s3_client

logger = logging.getLogger(__name__)


def s3_probe_client():
    return s3_client(
        connect_timeout=settings.READINESS_TIMEOUT_SECONDS,
        read_timeout=settings.READINESS_TIMEOUT_SECONDS,
        retries={"total_max_attempts": 1},
    )


def sqlite_probe():
    with connection(
        metadata_manager.db_path, mode="rw", busy_timeout=settings.READINESS_TIMEOUT_SECONDS
    ) as db:
        db.execute(select(literal(1))).first()
        db.execute(select(Observation.file_id).limit(1)).first()
        # Detect a writer lock/read-only volume without changing persisted data.
        db.execute("BEGIN IMMEDIATE")
        db.execute(update(Observation).values(file_id=Observation.file_id).where(false()))
        db.rollback()


def validate_storage():
    sqlite_probe()
    access_probe()
    if settings.STORAGE_BACKEND != "s3":
        return
    with closing(s3_probe_client()) as client:
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
                    with closing(s3_probe_client()) as client:
                        client.head_bucket(Bucket=settings.S3_BUCKET_BRONZE)
                self.ok = True
            except Exception as exc:
                logger.warning("Readiness dependency failed: %s", type(exc).__name__)
                self.ok = False
            self.expires = time.monotonic() + settings.READINESS_CACHE_SECONDS
            return self.ok


readiness = Readiness()
