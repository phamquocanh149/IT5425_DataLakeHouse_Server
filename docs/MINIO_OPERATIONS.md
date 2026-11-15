# MinIO deployment and recovery

Use the existing compose.yaml (Docker Desktop Linux containers, amd64). Copy missing
settings from .env.example into .env; use distinct randomly generated root and ingestion
secrets. Never commit .env. Native maintenance commands use S3_ENDPOINT=http://127.0.0.1:9000;
Compose overrides the endpoint to http://minio:9000. API keys remain unchanged.

```powershell
docker compose up -d minio
docker compose run --rm minio-init
docker compose up -d --build api
docker compose ps
```

MinIO uses a persistent named volume mounted at /data. API SQLite remains on the registry
volume; its existing bronze volume is retained for temporary files and rollback. Active
DuckDB files must also stay on persistent local/block storage. Export only consistent
snapshots to climate-warehouse. The Compose network connects services internally;
published ports are bound to loopback. Use existing HTTPS termination for remote Clients.

Console: http://127.0.0.1:9001 (root credentials from your private .env).
For mc inspection, start an interactive shell using the verified mc image:

```powershell
docker compose run --rm --entrypoint /bin/sh minio-init
```

Inside that shell (do not enable shell tracing):

```sh
mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc ls lake
mc version info lake/climate-bronze
mc anonymous get lake/climate-bronze
mc ls --recursive lake/climate-bronze
```

The initializer is idempotent. All four buckets are private and versioned. The dedicated
ingestion identity can list Bronze and GET/PUT only the four supported source prefixes;
it cannot delete raw or access Silver/Gold/Warehouse. Root credentials are not passed to
FastAPI. Versioning is defense in depth, not Object Lock: administrators can still alter
objects. The adapter uses conditional PUT (If-None-Match: *) to prevent overwrite.

## Migration

Stop ingestion before migration and target the registry actually used by your deployment.
Native commands default to this checkout's metadata directory; container commands target
/storage/metadata. Do not confuse the two. Existing native Bronze is not automatically
visible inside named Docker volumes.

```powershell
python scripts/migrate_metadata.py
python scripts/migrate_bronze_s3.py --dry-run
python scripts/migrate_bronze_s3.py --apply
python scripts/reconcile_storage.py --checksum
```

The first command imports legacy JSON using the existing Stage 0 migration with backups.
S3 migration creates a consistent SQLite backup, validates local SHA-256, conditionally
copies each object, downloads and hashes it again, then commits S3 mapping columns.
Local files, JSON metadata, stored_path and content_blobs rollback references are retained.
Re-running verifies existing mappings and skips copies. Inspect errors and reconcile
orphans after interruptions before resuming ingestion. Objects without matching metadata
are reported, never automatically removed. --repair-status changes only metadata status.

To consolidate native legacy JSON/raw into the Docker registry, mount the checkout's
data_lake and metadata read-only at /legacy/data_lake and /legacy/metadata in a one-shot
API container and run `python scripts/import_legacy_checkout.py --source /legacy`.
Review the inventory, then repeat with `--apply`. The importer backs up the existing
SQLite registry and copies only checksum-verified files without overwriting conflicts.
Run the S3 migration in that same registry volume afterwards.

Keys use scientific source_date and a SHA-256 encoding of dataset_key (so arbitrary Unicode
or path characters cannot escape a partition), revision and full content SHA-256:

```text
climate-bronze/source=usdm/year=2021/date=2021-06-22/dataset=<id-hash>/revision=1/sha256=<hash>/raw.zip
climate-silver/source=usdm/year=2021/part-0001.parquet       (reserved)
climate-gold/dataset=fct_drought_weekly/year=2021/...        (reserved)
climate-warehouse/{exports,snapshots,dbt-artifacts}/         (reserved)
```

## Backup and restore

1. Pause ingestion. Back up SQLite using sqlite3.Connection.backup() (as migration does),
   not a live copy of ingestion.sqlite3 alone: WAL may contain committed data.
2. Back up MinIO /data volume while MinIO is stopped, preserving the entire directory,
   ownership and .minio.sys. Alternatively use a version-aware object backup with an
   administrative backup identity; a simple current-object mirror does not preserve versions.
3. Store a protected backup of private environment configuration separately. Keep local
   Bronze and legacy metadata backups. Never use docker compose down -v on real data.
4. Restore MinIO volume and SQLite backup from the same paused checkpoint, using the
   pinned images and original settings. Restore ownership for API UID/GID 10001.
5. Start MinIO, run init, then reconciliation/checksums before starting ingestion.
   For pre-migration rollback restore the pre-migration SQLite backup and explicitly select
   STORAGE_BACKEND=local in native Server configuration; Compose intentionally always uses S3.

The SQLite writer lock spans S3 transfer for consistent revisions in this single-client
stage. SDK uses three total attempts, 3s connect and 10s read timeouts; outages return 503
without VERIFIED and the existing Client queue retries. A DB failure after upload can leave
an orphan: retry safely adopts it after hashing, or reconciliation reports it for review.

## Validation

```powershell
python -m pytest -q
python scripts/compose_smoke.py
```

Smoke creates unique test buckets, project, registry and random credentials, tests real
HTTPX/MinIO, then stops/removes only its containers/network. It deliberately retains its
isolated named volumes for inspection (no data deletion). The printed project prefix
identifies them. Do not run scripts/s3_assertions.py against production.
