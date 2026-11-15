# Storage backup, restore and native migration

Stop writers for a consistent pair of Bronze and SQLite snapshots. Do not copy only
ingestion.sqlite3 while a process is writing: WAL/SHM may contain committed state.
These commands are operator instructions; no existing production data was migrated.

## Backup Compose volumes (PowerShell)

Use the same project name/options as deployment. `docker compose create api` creates the
container/volumes without starting writers if necessary. Backup archives contain sensitive
raw data and metadata; store them privately. Each backup gets a fresh directory.

```powershell
docker compose stop api
$backupDir = Join-Path (Get-Location) ('backup-' + (Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Path $backupDir
docker compose run --rm --no-deps --user 0:0 --cap-add DAC_OVERRIDE --cap-add CHOWN --cap-add FOWNER --entrypoint tar -v "${backupDir}:/backup" api -czf /backup/storage.tgz -C /storage data_lake metadata
Get-FileHash (Join-Path $backupDir storage.tgz) -Algorithm SHA256
docker compose up -d --wait
```

Keep archive and checksum together. A stopped writer plus both directories preserves SQLite
WAL consistency and observation-to-blob paths. Temporary files are retained for reconciliation.

## Restore into NEW volumes, leaving existing data untouched

Validate the checksum and use only a trusted archive you created. Start from the same source
and keys, choose a new unused Compose project name, and keep the original deployment stopped
to avoid competing for port 8000. Never extract over an existing nonempty deployment.

```powershell
$restoreProject = 'climate-restore-' + (Get-Date -Format yyyyMMddHHmmss)
# Set $backupDir to the backup directory verified above.
docker compose -p $restoreProject create api
docker compose -p $restoreProject run --rm --no-deps --user 0:0 --cap-add DAC_OVERRIDE --cap-add CHOWN --cap-add FOWNER --entrypoint tar -v "${backupDir}:/backup:ro" api -xzf /backup/storage.tgz -C /storage
docker compose -p $restoreProject run --rm --no-deps --user 0:0 --cap-add DAC_OVERRIDE --cap-add CHOWN --cap-add FOWNER --entrypoint chown api -R 10001:10001 /storage/data_lake /storage/metadata
docker compose -p $restoreProject run --rm --no-deps api python scripts/reconcile_storage.py --checksum
docker compose -p $restoreProject up -d --wait
```

Review reconciliation output and authenticated `/uploads` before directing the Client to the
restored service. Always use `-p $restoreProject` thereafter. Keep original volumes and backup
until recovery is accepted. No automatic volume deletion is provided.

## Existing native data to Docker

Stop native Uvicorn and all upload writers. Back up the entire native `data_lake` and `metadata`
directories together; keep the original host directories. If JSON metadata needs migration,
run `scripts/migrate_metadata.py` with native settings first and review its backup/report.
Create a fresh Compose project as above. Create `storage.tgz` with the two relative top-level
directories `data_lake` and `metadata` (Windows `tar -czf storage.tgz data_lake metadata`, from
the native Server root, with writers stopped). Restore using the procedure above; ownership
must be adjusted to UID/GID 10001 because Windows archive ownership differs.

Default stored paths are relative (`data_lake/bronze/...`) and remain valid under `/storage`.
If historical settings used custom/absolute storage paths, inspect those records and plan an
explicit path mapping before migration; do not rewrite records or move/delete raw blindly.
Docker does not read the host `.env` storage paths: Compose deliberately mounts isolated
named volumes at `/storage/data_lake` and `/storage/metadata`. Pending Client jobs stay on
the native Client and must not be moved into the Server volumes.
