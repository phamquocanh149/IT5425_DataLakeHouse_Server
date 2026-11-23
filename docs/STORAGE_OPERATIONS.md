# Legacy local backend only

**This file applies ONLY to `STORAGE_BACKEND=local` (legacy native Server).**
It is NOT an S3 backup/restore runbook. Current `compose.yaml` forces `s3`:
API volume `bronze` contains temp/legacy files; actual objects live in `minio-data`.
An archive of `/storage/data_lake` + `/storage/metadata` is NOT a complete S3 backup.

## Single canonical S3 procedure

Follow [MINIO_OPERATIONS.md: Backup and restore](MINIO_OPERATIONS.md#backup-and-restore).
It requires a stopped full MinIO volume snapshot, SQLite Connection.backup(), a manifest
with checksums, fresh restore volumes, reconciliation and a recurring restore drill.
The old API-only Compose tar/restore commands have been removed to prevent accidental
restoration of a registry whose S3 objects were never backed up.

## Legacy local scope and migration notes

- Confirm the actual backend is local and observations do not depend on S3 mappings.
  If s3_object_key is populated, use the complete canonical S3 procedure.
- Pause the native API and all writers. Snapshot ingestion.sqlite3 AND access.sqlite3
  using sqlite3.Connection.backup() into new files. Preserve local Bronze, legacy JSON
  and metadata/backups from the same paused checkpoint. Do not copy a live DB without WAL.
- Keep an inventory of file_id/path/hash/size, archive checksums and a non-secret manifest;
  store private configuration separately with controlled access.
- Restore legacy into NEW directories with explicit STORAGE_BACKEND=local. Check both
  databases' integrity, every raw hash and reconciliation before resuming writers.
  Do not start current S3 Compose with only a local archive and call it a complete restore.
- To migrate to S3, preserve originals, dry-run scripts/migration/import_legacy_checkout.py before
  --apply, then use scripts/migration/migrate_bronze_s3.py and reconciliation as described in the
  MinIO runbook. Do not silently rewrite ownership/file_id/dataset_key/path conflicts.

These are legacy compatibility notes, not a second S3 runbook. Client pending snapshots
remain on the Client and must be preserved independently of Server deployment migration.
