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

**Canonical S3 runbook.** Do not use an API-only `/storage/data_lake` +
`/storage/metadata` archive as an S3 backup. Actual objects live in `minio-data`.
[STORAGE_OPERATIONS.md](STORAGE_OPERATIONS.md) is restricted to legacy local storage.
This procedure uses a complete STOPPED MinIO volume snapshot, not a current-object mirror.

### Policy, RPO/RTO and schedule

- Initial operational targets: **RPO <= 24 hours; RTO <= 2 hours**. These are targets
  requiring acceptance, not measured guarantees. Back up at least daily and before
  storage/schema releases. Alert when the latest verified off-host checkpoint is older
  than 24 hours. No scheduler is installed by this change; assign an operator to configure it.
- Run a restore drill **monthly**, and after image/schema/backup-tool changes. Record
  operator, checkpoint, start/end UTC, observations, checksums/version checks, actual RPO/RTO,
  PASS/FAIL and deviations in a report beside the bundle. Do not rewrite the manifest.
- Actual RPO = incident time minus latest complete verified off-host checkpoint.
  Actual RTO = recovery start until the restored API is ready AFTER all reconciliation gates.
  If targets fail, record the failure and review backup frequency/capacity with the owner.
- Pause Client workers/producers, API and ALL migration/reconcile/admin writers. Let in-flight
  requests finish; stop API before MinIO. Keep Client pending snapshots for replay after restore.
  Do not force-kill writers to obtain a supposedly consistent checkpoint.
- Copy the entire stopped MinIO `/data`, including `.minio.sys`, versions and all buckets.
  Do not assume `mc mirror --versions` is supported or preserves all versions/delete markers
  on the installed mc release. A different version-aware backup solution needs its own drill;
  it is not a second supported procedure in this runbook.

### 1. Select the deployment, stop writers and identify mounts/images

PowerShell from Server root, Linux Docker engine. Replace the project placeholder and use
EXACTLY the compose files used by the source deployment (including compose.source.yaml if
applicable). Do not switch deployment type. The helper uses the existing API's immutable
image ID and bind-mounts the backup script; no package installation is needed.

```powershell
function D {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw 'Docker command failed; stop this procedure' }
}
$sourceProject = '<existing-project-name>'
$sourceCompose = @('-p', $sourceProject, '-f', 'compose.yaml') # use the actual deployment file
$apiId = (D compose @sourceCompose ps -aq api).Trim()
$minioId = (D compose @sourceCompose ps -aq minio).Trim()
$initId = (D compose @sourceCompose ps -aq minio-init).Trim()
if (!$apiId -or !$minioId -or !$initId) { throw 'Expected existing deployment containers' }
$apiImage = (D inspect --format '{{.Image}}' $apiId).Trim()
$minioImage = (D inspect --format '{{.Image}}' $minioId).Trim()
$mcImage = (D inspect --format '{{.Image}}' $initId).Trim()
$apiMounts = (D inspect --format '{{json .Mounts}}' $apiId) | ConvertFrom-Json
$minioMounts = (D inspect --format '{{json .Mounts}}' $minioId) | ConvertFrom-Json
$registryVolume = ($apiMounts | Where-Object Destination -eq '/storage/metadata').Name
$legacyVolume = ($apiMounts | Where-Object Destination -eq '/storage/data_lake').Name
$minioVolume = ($minioMounts | Where-Object Destination -eq '/data').Name
if (!$registryVolume -or !$legacyVolume -or !$minioVolume) { throw 'Named volume mapping missing' }
# Pause external workers/maintenance first; retain pending payloads.
D compose @sourceCompose stop -t 180 api
D compose @sourceCompose stop -t 180 minio
foreach ($id in @($apiId, $minioId)) {
    if ((D inspect --format '{{.State.Running}}' $id).Trim() -ne 'false') { throw 'Writer still running' }
}
```

Do not print full inspect/config output: it may expose credentials. Confirm no separate
maintenance containers/processes use these volumes. `--writers-stopped` below is an operator
assertion, not proof automatically obtained by the offline helper. Check graceful stop status
and logs before declaring the checkpoint safe.

### 2. Create and verify the complete bundle

```powershell
$backupRoot = Join-Path (Get-Location) ('backup-' + (Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Path $backupRoot -ErrorAction Stop | Out-Null
$backupScript = (Resolve-Path scripts/storage_backup.py).Path
D run --rm --network none --user 0:0 --entrypoint python `
  --mount "type=volume,source=$registryVolume,target=/registry,readonly" `
  --mount "type=volume,source=$minioVolume,target=/minio,readonly" `
  --mount "type=volume,source=$legacyVolume,target=/legacy,readonly" `
  --mount "type=bind,source=$backupRoot,target=/backup" `
  --mount "type=bind,source=$backupScript,target=/tool/storage_backup.py,readonly" `
  $apiImage /tool/storage_backup.py create --bundle /backup/checkpoint `
  --registry /registry --minio /minio --legacy /legacy --writers-stopped `
  --project $sourceProject --image "api=$apiImage" --image "minio=$minioImage" --image "mc=$mcImage"
```

`scripts/storage_backup.py` calls SQLite `Connection.backup()` for BOTH `ingestion.sqlite3`
and `access.sqlite3`, checks integrity and closes connections before archiving. It retains
legacy metadata/backups but replaces the live database/WAL/SHM with consistent snapshots.
The bundle contains `registry.tar.gz`, `minio-data.tar.gz`, `legacy.tar.gz`, `manifest.json`
and `manifest.sha256`. The manifest records UTC checkpoint, project/image IDs, schema version,
observation IDs/hash/size/revision/S3 mapping, and each archive's SHA-256 and size.
Missing manifest, missing archive or checksum failure means the bundle is INVALID, even if
some files were written successfully. Never edit the manifest to bypass a failed verification.
The helper rejects archive links, path traversal and special files.

Store a protected copy OUTSIDE the host/volumes being backed up. Verify the copied bundle:
`python scripts/storage_backup.py verify --bundle <off-host-copy>`.
Checksums detect corruption, not malicious replacement: protect both manifest and checksum.
Store private configuration/API_KEYS/S3 credentials and KMS material, if applicable, separately
with controlled access. Preserve the exact release source/Compose and image artifacts/provenance;
image IDs in the manifest alone do not make images available on a replacement host.
Only after the off-host copy verifies, resume the original deployment:

```powershell
D compose @sourceCompose up -d minio
D compose @sourceCompose run --rm minio-init
D compose @sourceCompose up -d --wait api
```

If backup fails, retain source volumes, record the failed checkpoint and inspect source state
before resuming service. A partial bundle must never replace the last accepted backup.

### 3. Restore to NEW empty volumes

Use the verified checkpoint, original bucket names/config and matching images/release.
Choose a new unused project and a separate loopback-port override so a drill cannot collide
with the source. Example `restore.ports.yaml` (requires Compose >=2.24.4):

```yaml
services:
  api:
    ports: !override
      - "127.0.0.1:18000:8000"
  minio:
    ports: !override
      - "127.0.0.1:19000:9000"
      - "127.0.0.1:19001:9001"
```

Use the same base compose variant as the source; never point real Clients at the drill.
Create containers/volumes only: do not start MinIO or run init on empty restore volumes.

```powershell
$restoreProject = 'climate-restore-' + (Get-Date -Format yyyyMMddHHmmss)
# restore.ports.yaml must use separate loopback ports.
$restoreCompose = @('-p', $restoreProject, '-f', 'compose.yaml', '-f', 'restore.ports.yaml')
D compose @restoreCompose create api minio minio-init  # create only; do not start/init yet
$restoreApiId = (D compose @restoreCompose ps -aq api).Trim()
$restoreMinioId = (D compose @restoreCompose ps -aq minio).Trim()
$restoreApiMounts = (D inspect --format '{{json .Mounts}}' $restoreApiId) | ConvertFrom-Json
$restoreMinioMounts = (D inspect --format '{{json .Mounts}}' $restoreMinioId) | ConvertFrom-Json
$restoreRegistry = ($restoreApiMounts | Where-Object Destination -eq '/storage/metadata').Name
$restoreLegacy = ($restoreApiMounts | Where-Object Destination -eq '/storage/data_lake').Name
$restoreMinio = ($restoreMinioMounts | Where-Object Destination -eq '/data').Name
if (!$restoreRegistry -or !$restoreLegacy -or !$restoreMinio) { throw 'Missing restore volumes' }
if ($restoreRegistry -eq $registryVolume -or $restoreLegacy -eq $legacyVolume -or $restoreMinio -eq $minioVolume) {
    throw 'Restore must not target source volumes'
}
D run --rm --network none --user 0:0 --entrypoint python `
  --mount "type=volume,source=$restoreRegistry,target=/registry" `
  --mount "type=volume,source=$restoreMinio,target=/minio" `
  --mount "type=volume,source=$restoreLegacy,target=/legacy" `
  --mount "type=bind,source=$backupRoot,target=/backup,readonly" `
  --mount "type=bind,source=$backupScript,target=/tool/storage_backup.py,readonly" `
  $apiImage /tool/storage_backup.py restore --bundle /backup/checkpoint `
  --registry /registry --minio /minio --legacy /legacy --writers-stopped
D run --rm --network none --user 0:0 --entrypoint chown `
  --mount "type=volume,source=$restoreRegistry,target=/registry" `
  --mount "type=volume,source=$restoreLegacy,target=/legacy" `
  $apiImage -R 10001:10001 /registry /legacy
```

The restore helper verifies ALL archives before writing and refuses nonempty or nested target
paths. It preserves archived ownership; API database snapshots need the explicit UID/GID 10001
adjustment above. Keep MinIO ownership as archived. If interrupted, preserve partial volumes
for inspection and retry in a NEW project; do not overlay partial state or delete the source.

### 4. Acceptance gates and cutover

1. Record recovery start UTC. Start restored MinIO, then run init using original bucket names
   and credentials. Keep the restored API stopped. Do not change retention/policy incidentally.
2. Run `D compose @restoreCompose run --rm --no-deps api python scripts/reconcile_storage.py --checksum`.
   The registry is restored already; do not create a fresh database. Do not use `--repair-status`
   to hide restore failures. No missing/corrupt/unmigrated rows are acceptable. Explain any
   orphan against the pre-backup inventory; never auto-delete it.
3. Compare ALL observation IDs/revisions/hash/size/S3 mappings against the manifest and check
   `PRAGMA integrity_check=ok` for both SQLite databases. With an administrative backup identity,
   list object versions, GET historical versions and verify hashes/delete markers as applicable.
   Default reconciliation verifies current objects, NOT the complete version history.
4. Start restored API; require `/readyz` 200. Using a test Client and appropriate identity,
   re-upload an observation already in the backup: expect DUPLICATE with the same file_id and
   no extra revision. Check ownership and accounting remain intact. Do not modify scientific
   source data or production to generate evidence.
5. Record actual RTO when the API is ready after validation; compute RPO from the off-host
   checkpoint. Save the drill/incident report beside the immutable manifest.
6. Only then cut over real Clients, preserving pending jobs for replay after the checkpoint.
   A drill does NOT cut over: stop only the restore project's containers and retain its volumes
   and evidence. No script automatically changes DNS/tunnels/keys or removes source volumes.

**Stage 2 evidence:** offline tests exercise actual SQLite/WAL backup and restore with fixture
version-directory bytes, and reject corrupted/incomplete bundles. They do not prove a working
MinIO restore. Docker engine was unavailable during this change, so a real MinIO drill and
measured RPO/RTO remain **Needs Verification**. Recurring scheduling is not configured yet.

### Stage 2 S3 transaction changes

Schema initialization/migration runs at startup or an explicit migration CLI, never in request
connections. Upload reads a snapshot, publishes and GET-verifies outside any transaction, then
opens a short BEGIN IMMEDIATE to re-check ownership/hash/revision and commit. Concurrent changes
retry at most eight rounds. Default registry lock wait is 0.5s; contention returns HTTP 503 with
Retry-After: 1. The existing Client retries 503 using its own backoff, not the header yet.
Speculative objects from losing races or DB rollback remain for reconciliation; raw is not deleted.
S3 migration/reconciliation also performs network I/O before a short guarded commit and rejects
changed registry snapshots. Pause writers for authoritative maintenance: an in-flight speculative
object may not yet have a registry row even if the row snapshot itself has not changed.

## Validation

```powershell
python -m pytest -q
python scripts/compose_smoke.py
```

Smoke creates unique test buckets, project, registry and random credentials, tests real
HTTPX/MinIO, then stops/removes only its containers/network. It deliberately retains its
isolated named volumes for inspection (no data deletion). The printed project prefix
identifies them. Do not run scripts/s3_assertions.py against production.

## Stage 5: deployments with Medallion products

The Stage 2 bundle above is not a complete backup of USDM products/warehouse.
Use [Stage 5 checkpoint and restore](STAGE5_PRODUCTION_READINESS.md) when those exist:
all historical products/recipes, registry, warehouse, stopped MinIO volume, and a
pre-stop inventory of all object versions/delete markers must be captured together.
Do not mark real MinIO/off-host RPO/RTO acceptance complete from a local restore test.
