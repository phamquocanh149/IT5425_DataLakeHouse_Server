"""Isolated real MinIO full-volume restore using exact API/worker release images.

Requires Docker Linux. Creates only unique test containers/network/volume; retains the
test volume for inspection. Does not connect to workstation MinIO or production data.
"""

import hashlib
import json
import os
import re
import subprocess
import time
import uuid


def main():
    digest = os.environ.get("MINIO_DIGEST", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("MINIO_DIGEST must be the verified official digest")
    api, worker = os.environ["CLIMATE_API_IMAGE"], os.environ["CLIMATE_WORKER_IMAGE"]
    image = "quay.io/minio/minio@" + digest
    prefix = "stage5-restore-" + uuid.uuid4().hex[:10]
    network, volume = prefix + "-net", prefix + "-data"
    old, new, api_name = (prefix + suffix for suffix in ("-old", "-new", "-api"))
    password = uuid.uuid4().hex
    base = {
        "DEBUG": "False",
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET_BRONZE": "drill-bronze",
        "S3_ACCESS_KEY": "drill-root",
        "S3_SECRET_KEY": password,
        "ENABLE_STATIC_KEYS": "False",
        "REQUIRE_SSE_KMS": "False",
        "REQUIRE_OBJECT_LOCK": "False",
        "DATA_LAKE_DIR": "data_lake",
        "METADATA_DIR": "metadata",
        "TEMP_DIR": "data_lake/temp",
        "API_KEYS": json.dumps(
            [
                {
                    "key_id": "restore",
                    "secret_hash": hashlib.sha256(b"fixture-secret").hexdigest(),
                    "client_id": "usdm-replay",
                    "role": "collector",
                    "enabled": True,
                    "expires_at": "2050-01-01T00:00:00Z",
                    "sources": ["usdm"],
                }
            ]
        ),
    }

    def docker(*args):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
        return result.stdout.strip()

    def env_args(values):
        return [arg for key, value in values.items() for arg in ("-e", key + "=" + value)]

    def helper(*command, restored=False, user="0"):
        env = {
            **base,
            "BASE_DIR": "/drill/restored" if restored else "/drill/runtime",
            "S3_ENDPOINT": "http://restored-minio:9000" if restored else "http://source-minio:9000",
        }
        # Root only for this isolated storage helper, to preserve full-volume ownership.
        return docker(
            "run",
            "--rm",
            "--user",
            user,
            "--network",
            network,
            "-v",
            volume + ":/drill",
            *env_args(env),
            worker,
            "python",
            *command,
        )

    containers = []
    docker("network", "create", network)
    try:
        docker("volume", "create", volume)
        for reference in (api, worker):
            docker("image", "inspect", reference)
        containers.append(old)
        docker(
            "run",
            "-d",
            "--name",
            old,
            "--network",
            network,
            "--network-alias",
            "source-minio",
            "-v",
            volume + ":/drill",
            "-e",
            "MINIO_ROOT_USER=drill-root",
            "-e",
            "MINIO_ROOT_PASSWORD=" + password,
            image,
            "server",
            "/drill/minio-original",
        )
        helper("scripts/smoke/s3_recovery_fixture.py", "seed")
        docker("stop", old)
        helper(
            "scripts/backup/medallion_backup.py",
            "create",
            "--root",
            "/drill/runtime",
            "--bundle",
            "/drill/checkpoint",
            "--minio",
            "/drill/minio-original",
            "--s3-inventory",
            "/drill/versions.json",
            "--writers-stopped",
            "--image",
            image,
            "--image",
            docker("image", "inspect", "--format", "{{.Id}}", api),
            "--image",
            docker("image", "inspect", "--format", "{{.Id}}", worker),
        )
        started = time.monotonic()
        helper(
            "scripts/backup/medallion_backup.py",
            "restore",
            "--bundle",
            "/drill/checkpoint",
            "--root",
            "/drill/restored",
        )
        containers.append(new)
        docker(
            "run",
            "-d",
            "--name",
            new,
            "--network",
            network,
            "--network-alias",
            "restored-minio",
            "-v",
            volume + ":/drill",
            "-e",
            "MINIO_ROOT_USER=drill-root",
            "-e",
            "MINIO_ROOT_PASSWORD=" + password,
            image,
            "server",
            "/drill/restored/minio",
        )
        helper("scripts/smoke/s3_recovery_fixture.py", "wait", restored=True)
        # API retains its production non-root UID; MinIO subtree ownership is unchanged.
        helper(
            "-c",
            "import os; from pathlib import Path; "
            "root=Path('/drill/restored'); os.chown(root,10001,10001); "
            "[(root/d).mkdir(parents=True,exist_ok=True) for d in ('metadata','data_lake','products','recipes')]; "
            "[(os.chown(p,10001,10001)) for d in ('metadata','data_lake','products','recipes') "
            "for p in ([root/d]+list((root/d).rglob('*'))) if p.exists()]",
            restored=True,
        )
        containers.append(api_name)
        env = {**base, "BASE_DIR": "/drill/restored", "S3_ENDPOINT": "http://restored-minio:9000"}
        docker(
            "run",
            "-d",
            "--name",
            api_name,
            "--network",
            network,
            "--network-alias",
            "restored-api",
            "-v",
            volume + ":/drill",
            *env_args(env),
            api,
        )
        result = helper(
            "scripts/smoke/s3_recovery_fixture.py", "verify", restored=True, user="10001:10001"
        )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "scope": "isolated same-host drill, not off-host acceptance",
                    "service_recovery_seconds": time.monotonic() - started,
                    "retained_volume": volume,
                    "verification": result,
                },
                indent=2,
            )
        )
    finally:
        for container in reversed(containers):
            subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)


if __name__ == "__main__":
    main()
