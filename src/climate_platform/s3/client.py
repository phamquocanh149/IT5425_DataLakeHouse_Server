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
    access_key=None,
    secret_key=None,
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
        aws_access_key_id=access_key if access_key is not None else settings.S3_ACCESS_KEY,
        aws_secret_access_key=secret_key if secret_key is not None else settings.S3_SECRET_KEY,
        config=Config(**options),
    )


def medallion_credentials():
    """Resolve the dedicated least-privilege Silver/Gold publisher identity."""
    access = settings.MEDALLION_S3_ACCESS_KEY
    secret = settings.MEDALLION_S3_SECRET_KEY
    if not access or not secret:
        raise RuntimeError("MEDALLION_S3_ACCESS_KEY and MEDALLION_S3_SECRET_KEY are required")
    return access, secret


def medallion_client():
    """boto3 client for reading Bronze and writing Silver/Gold/Warehouse."""
    access, secret = medallion_credentials()
    return s3_client(
        connect_timeout=10,
        read_timeout=120,
        retries={"mode": "standard", "total_max_attempts": 5},
        access_key=access,
        secret_key=secret,
    )
