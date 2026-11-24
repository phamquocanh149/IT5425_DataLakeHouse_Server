"""Real Compose smoke test; isolated fake credentials, project and persistent volumes.

Requires Docker Compose >=2.24.4 and the sibling Client checkout.
Stops its containers but deliberately retains test volumes for inspection.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    client_root = Path(os.environ.get("CLIENT_REPO_PATH", ROOT.parent / "climate-collector"))
    if not (client_root / "client/api_client.py").is_file():
        raise RuntimeError("Set CLIENT_REPO_PATH to the Client checkout")
    sys.path.insert(0, str(client_root))
    from client.api_client import APIClient
    from client.config import Config
    from client.uploader import upload_file
    from client.uploader import enqueue_file, send_job, UploadError

    project = "climate-smoke-" + uuid.uuid4().hex[:10]
    env = dict(
        os.environ,
        COLLECTOR_API_KEY="smoke-only-collector",
        ADMIN_API_KEY="smoke-only-admin",
        MINIO_ROOT_USER="smoke-root",
        MINIO_ROOT_PASSWORD=uuid.uuid4().hex,
        S3_ACCESS_KEY="smoke-ingestion",
        S3_SECRET_KEY=uuid.uuid4().hex,
        MINIO_API_PORT="0",
        MINIO_CONSOLE_PORT="0",
        S3_BUCKET_BRONZE=project + "-bronze",
        S3_BUCKET_SILVER=project + "-silver",
        S3_BUCKET_GOLD=project + "-gold",
        S3_BUCKET_WAREHOUSE=project + "-warehouse",
    )
    scratch = ROOT / ".smoke"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        temp = Path(directory)
        empty = temp / "empty.env"
        empty.write_text("")
        override = temp / "override.yaml"
        override.write_text(
            "services:\n  api:\n"
            + (
                "    image: " + json.dumps(env["CLIMATE_API_IMAGE"]) + "\n    pull_policy: never\n"
                if env.get("CLIMATE_API_IMAGE")
                else ""
            )
            + '    ports: !override\n      - "127.0.0.1:0:8000"\n'
            '    environment:\n      COLLECTOR_SOURCES: \'["usdm","noaa","usgs","nldas"]\'\n'
        )
        command = [
            "docker",
            "compose",
            "--env-file",
            str(empty),
            "-p",
            project,
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
        ]

        def compose(*args):
            result = subprocess.run(
                command + list(args), cwd=ROOT, env=env, capture_output=True, text=True, timeout=600
            )
            if result.returncode:
                raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
            return result.stdout.strip()

        def connect():
            address = compose("port", "api", "8000").splitlines()[0]
            return APIClient(
                Config(
                    "collector01",
                    "all",
                    "http://" + address,
                    "smoke-only-collector",
                    retries=0,
                    root=temp / "client",
                )
            )

        def verify_storage(count=2):
            code = """
import json, sqlite3
from climate_platform.s3.minio_repository import S3Storage
storage=S3Storage()
db=sqlite3.connect('/storage/metadata/ingestion.sqlite3')
db.row_factory=sqlite3.Row
rows=[dict(r) for r in db.execute('SELECT * FROM observations')]
assert len(rows)==EXPECTED
assert {r['source'] for r in rows}=={'usdm','noaa'}
for row in rows:
    assert row['s3_bucket']==storage.bucket
    assert row['stored_path']==f"s3://{storage.bucket}/{row['s3_object_key']}"
    storage.verify(row['s3_object_key'],row['sha256'],row['size_bytes'])
    assert row['status']=='VERIFIED'
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print(json.dumps(sorted(r['file_id'] for r in rows)))
"""
            return json.loads(
                compose("exec", "-T", "api", "python", "-c", code.replace("EXPECTED", str(count)))
            )

        try:
            compose(
                "up",
                "-d",
                *(["--no-build"] if env.get("CLIMATE_API_IMAGE") else ["--build"]),
                "--wait",
                "--wait-timeout",
                "120",
            )
            compose("run", "--rm", "minio-init")  # Idempotency of provisioning.
            import boto3
            from botocore.exceptions import ClientError

            endpoint = "http://" + compose("port", "minio", "9000").splitlines()[0]
            admin = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=env["MINIO_ROOT_USER"],
                aws_secret_access_key=env["MINIO_ROOT_PASSWORD"],
                region_name="us-east-1",
            )
            buckets = {b["Name"] for b in admin.list_buckets()["Buckets"]}
            assert buckets == {
                env["S3_BUCKET_" + name] for name in ("BRONZE", "SILVER", "GOLD", "WAREHOUSE")
            }
            for bucket in buckets:
                assert admin.get_bucket_versioning(Bucket=bucket)["Status"] == "Enabled"
                try:
                    admin.get_bucket_policy(Bucket=bucket)
                    raise AssertionError("Unexpected bucket policy")
                except ClientError as exc:
                    assert exc.response["Error"]["Code"] == "NoSuchBucketPolicy"
            sample = temp / "sample.csv"
            sample.write_bytes(b"date,value\n2021-06-22,1.2\n")
            api = connect()
            try:
                assert api.health().json()["status"] == "ok"
                for source in ("usdm", "noaa"):
                    first = upload_file(api, sample, source, "2021-06-22")
                    assert first["server_status"] == "VERIFIED"
                    assert (
                        first["server_metadata"]["sha256"]
                        == hashlib.sha256(sample.read_bytes()).hexdigest()
                    )
                    assert (
                        upload_file(api, sample, source, "2021-06-22")["server_status"]
                        == "DUPLICATE"
                    )
            finally:
                api.close()
            before = verify_storage()
            import httpx

            obj = admin.list_objects_v2(Bucket=env["S3_BUCKET_BRONZE"])["Contents"][0]["Key"]
            assert (
                httpx.get(endpoint + "/" + env["S3_BUCKET_BRONZE"] + "/" + obj).status_code == 403
            )
            assert len(admin.list_object_versions(Bucket=env["S3_BUCKET_BRONZE"])["Versions"]) == 2
            compose("restart", "api")
            compose("up", "-d", "--wait", "--wait-timeout", "120")
            assert verify_storage() == before
            compose("down")  # No -v: prove named volumes survive container removal.
            compose("up", "-d", "--wait", "--wait-timeout", "120")
            assert verify_storage() == before
            api = connect()
            try:
                assert (
                    upload_file(api, sample, "usdm", "2021-06-22")["server_status"] == "DUPLICATE"
                )
            finally:
                api.close()
            assert verify_storage() == before
            api = connect()
            try:
                sample.write_bytes(b"date,value\n2021-06-22,2.4\n")
                revision = upload_file(api, sample, "usdm", "2021-06-22")
                assert revision["server_metadata"]["revision"] == 2
                verify_storage(3)  # Also downloads the previous revision again.
                compose("stop", "minio")
                job = enqueue_file(api.config, sample, "noaa", "2021-06-23")
                try:
                    send_job(api, job, immediate_retries=0)
                    raise AssertionError("Upload must fail while MinIO is stopped")
                except UploadError as exc:
                    assert exc.retryable
                pending = json.loads(
                    (api.config.root / "data/pending" / job / "metadata.json").read_text()
                )
                assert pending["http_status"] == 503
                compose("start", "minio")
                compose("up", "-d", "--wait", "--wait-timeout", "120")
                assert send_job(api, job)["server_status"] == "VERIFIED"
                verify_storage(4)
            finally:
                api.close()
            print(compose("exec", "-T", "api", "python", "scripts/smoke/s3_assertions.py"))
            print(
                "PASS: HTTPX Client -> FastAPI -> MinIO, SHA256/SQLite, duplicate/revision, outage/queue retry, restart/down-up persistence"
            )
        finally:
            compose("down")
            print("Retained isolated test volumes: " + project + "_{bronze,registry,minio-data}")


if __name__ == "__main__":
    main()
