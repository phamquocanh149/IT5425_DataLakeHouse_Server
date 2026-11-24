"""Shared boto3 S3 client factory (endpoint/credentials from Settings).

The single place the MinIO/S3 client is configured, so the object repository and the
readiness probe do not each rebuild the same client.
"""

import boto3
from botocore.config import Config

from climate_platform.config import settings


def s3_client(
    *,
    connect_timeout=3,
    read_timeout=10,
    retries=None,
    signature_version=None,
):
    options = {
        "connect_timeout": connect_timeout,
        "read_timeout": read_timeout,
        "retries": retries or {"mode": "standard", "total_max_attempts": 3},
        "s3": {"addressing_style": "path"},
    }
    if signature_version:
        options["signature_version"] = signature_version
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(**options),
    )
