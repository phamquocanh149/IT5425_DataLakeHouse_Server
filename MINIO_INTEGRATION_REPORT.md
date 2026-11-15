# MinIO integration report — 2026-11-15 (Asia/Saigon)

## Result

Integrated MinIO into the existing climate-platform Compose stack. The live API and MinIO
are healthy. Four private versioned buckets exist. All three existing observations were
migrated and independently downloaded/hash-verified; reconciliation reports no missing,
corrupt, unmigrated or orphan objects. Client API contract is unchanged. No Silver/Gold
ETL, Git push, firewall changes, deletion of legacy data or CPU emulation was performed.

Both repositories already had extensive uncommitted Stage 0–1 work; that work was retained.

## Images actually verified

Docker Desktop Engine 29.9.3, Linux/amd64 (Windows/amd64 CLI). Queried Docker Hub tag API,
registry manifests, pulled the exact platform digests, inspected configuration and ran both
binaries with no network and read-only rootfs before integration.

| Image | Discovered tags | Selected platform manifest |
|---|---|---|
| noname12346767/my-minio | latest: amd64/arm64; RELEASE.2025-10-15: arm64 only | linux/amd64, `sha256:ff3fdcaaf08a067191989010ad2862da14e0238973f6586750d740adb6d589bc` |
| noname12346767/mc-allos | latest: amd64/arm64/arm-v7 | linux/amd64, `sha256:18a6fc4d2af4807386cd0a76d1a7078144c8ad46a7eb6ed1bd6577b902a34c6d` |

No compatible versioned tag was available for amd64, so Compose pins immutable platform
digests discovered from the indexes, never floating latest. Index digests at verification:
server `sha256:b9fe219fc1ed7f60a102ab7a129d3becb9545a5a84a58020c7a76c983b72474c`;
mc `sha256:8ca8fec932fbbfaf6e8f7639cd9c0c3607553efcec3556b3b674f9a87ed4db1c`.

Server entrypoint `/usr/bin/docker-entrypoint.sh`, Cmd `minio`; tested command
`server /data --console-address :9001`. Binary reports RELEASE.2026-02-12T20-18-48Z,
commit `7aac2a2c5b7c882e68c1ce017d8256be2feea27f`, Go 1.24.13.
No curl is present; healthcheck uses verified bash and an HTTP readiness request.

mc entrypoint `mc`, no Cmd; `/usr/bin/mc` and `/bin/sh` verified. Binary reports
RELEASE.2025-08-13T08-35-41Z, commit DEVELOPMENT.GOGET, Go 1.24.13. The initializer
explicitly overrides entrypoint to `/bin/sh /init/minio-init.sh`.

### Provenance and vulnerability findings

Docker Hub descriptions/source descriptions are empty for both third-party repositories.
OCI labels claim MinIO licensing/vendor and an upstream server commit, and the indexes
contain attestation manifests, but a trusted publisher signature/source build chain was
**not verified**. Labels alone do not establish authenticity.

Docker Scout v1.28.0 was run on both exact digests, filtering Critical/High:

- Server: CLI reports 17 vulnerable packages / 76 unique vulnerabilities. Markdown header
  counts 16 Critical + 67 High package findings (83 occurrences, not 83 unique CVEs).
- mc: CLI reports 9 vulnerable packages / 53 unique vulnerabilities. Markdown header
  counts 13 Critical + 47 High package findings (60 occurrences).

Full evidence: [server scan](docs/security/minio-cves.md), [mc scan](docs/security/mc-cves.md).
Functional validation passed, but these images are **not security-cleared for production**.
No substitute image was selected; publisher remediation/provenance verification remains
an external deployment concern. Local services bind only to loopback.

## Files changed for this task

- `.env.example`, private ignored `.env`: pinned images and generated separate credentials.
- `compose.yaml`, `scripts/minio-init.sh`: persistent MinIO, readiness, one-shot provisioning,
  four private versioned buckets, Bronze-only ingestion identity and dependency ordering.
- `requirements.txt`: pinned boto3, botocore and s3transfer.
- `server/config.py`, `server/storage.py`, `server/metadata.py`, `server/ingestion.py`:
  S3 default, immutable conditional PUT, streamed download hashing, additive SQLite S3
  mapping columns and threadpool execution for blocking storage/registry work.
- `server/maintenance.py`, `server/s3_maintenance.py`, `scripts/reconcile_storage.py`,
  `scripts/migrate_bronze_s3.py`, `scripts/import_legacy_checkout.py`: conservative migration,
  backup, dry-run, orphan/mapping/integrity reconciliation and legacy consolidation.
- `tests/conftest.py`, `tests/test_s3_keys.py`, `scripts/compose_smoke.py`,
  `scripts/s3_assertions.py`: legacy regression mode, safe keys and actual MinIO tests.
- `.github/workflows/ci.yml`: existing Compose smoke now exercises S3 and retains its log.
- `README.md`, `docs/MINIO_OPERATIONS.md`, this report and `docs/security/*`.

The original local backend remains available only by explicit configuration for legacy
regression/rollback. Compose always selects S3; there is no automatic local fallback.
SQLite uses additive nullable s3_bucket/s3_object_key/s3_version_id columns; legacy schema
version 1 and paths remain readable. Observations are authoritative S3 mappings;
content_blobs retains legacy content-level dedup and rollback references.

## Bucket layout

```text
MinIO /data -> climate-platform_minio-data
├── climate-bronze
│   └── source=<source>/year=<year>/date=<source_date>/dataset=<dataset-id-sha256>/
│       revision=<n>/sha256=<content-sha256>/raw.<extension>
├── climate-silver     source=<source>/year=<year>/...       [reserved, empty]
├── climate-gold       dataset=<mart>/year=<year>/...        [reserved, empty]
└── climate-warehouse  exports/ snapshots/ dbt-artifacts/   [reserved, empty]
SQLite -> climate-platform_registry, /storage/metadata/ingestion.sqlite3
Legacy raw + temp -> existing climate-platform_bronze
```

## Migration completed

Inventory found two legacy JSON/raw pairs in the native checkout and one observation in
the already-running API's Docker volume. Paused the old API, backed up its registry,
copied the native files read-only into the active storage without overwriting conflicts,
and imported their JSON into the existing registry. Dry-run listed exactly three candidates.
Applied S3 migration, downloaded each object and checked SHA-256 and size, then committed
mapping columns. No local file, JSON or old path was deleted or replaced.

Migration backup in registry volume:
`/storage/metadata/backups/s3-aa727d53760c4821ac6e9d713ba38a85/ingestion.sqlite3`.
Legacy JSON backup: `/storage/metadata/backups/20261115T095713-5c09f68f`.
An additional `before-import-*` SQLite backup precedes consolidation.

Re-run dry-run: 3 skipped/verified, 0 new copies, 0 errors. Live reconciliation:
missing=[], corrupt=[], unmigrated=[], orphan_objects=[]. Authenticated live `/uploads`
returns all three S3 mappings. The authoritative active registry is the Docker volume,
not a new registry in the native checkout.

## Executed validation

| Check | Result |
|---|---|
| Server pytest (including legacy Stage 0–1 and safe S3 keys) | PASS: 35 tests |
| Client pytest, unchanged client source | PASS: 48 tests |
| Ruff check and formatting | PASS |
| Both mandatory images pull/inspect/start natively | PASS |
| mc initializer twice; exactly 4 private/versioned buckets | PASS |
| Anonymous GET denied; ingestion delete/Silver access denied | PASS |
| Actual sibling HTTPX Client → API → S3; SQLite mappings; download SHA-256 | PASS |
| Duplicate doesn't add observation or object version; revision retains prior bytes | PASS |
| MinIO stopped → HTTP 503, pending queue preserved; start → same job succeeds | PASS |
| API restart and Compose down/up preserve registry and S3 data | PASS |
| Real S3 PUT + injected SQLite commit failure → orphan detected and retry adopted | PASS |
| Conditional PUT refuses overwrite; incorrect mapping detected | PASS |
| Four simultaneous uploads → one VERIFIED, three DUPLICATE | PASS |
| Corrupt bytes with forged SHA-256 metadata detected; status repair after recovery | PASS |
| Migration backup/dry-run/checksum/idempotency and original file retained | PASS |
| Live migration of 3 observations + clean reconciliation | PASS |
| Whole Docker Desktop daemon restart | NOT RUN; tested container restart/recreation instead |
| Trusted publisher signature and CVE-free images | NOT VERIFIED / CVEs FOUND |

Tests use unique `climate-smoke-*` Compose projects, four unique buckets, SQLite volumes,
random credentials and random loopback ports. Cleanup stops/removes their containers and
networks but deliberately retains isolated named volumes (no user data deletion).
Successful projects: climate-smoke-fe1b218942, climate-smoke-93ab940190, and final expanded
suite climate-smoke-021badd1b1.
GitHub-hosted CI workflow was updated but not executed remotely from this session.

## Run and inspect

```powershell
docker compose up -d --build --wait
docker compose ps
docker compose exec -T api python scripts/reconcile_storage.py --checksum
docker compose run --rm --entrypoint /bin/sh minio-init
```

In the mc shell:

```sh
mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc ls lake
mc ls --recursive lake/climate-bronze
mc version info lake/climate-bronze
mc anonymous get lake/climate-bronze
```

API: http://127.0.0.1:8000; S3: http://127.0.0.1:9000;
Console: http://127.0.0.1:9001. Private credentials are in ignored `.env` and were not
printed or committed. Full deployment/backup/restore/rollback procedure:
[MINIO_OPERATIONS.md](docs/MINIO_OPERATIONS.md).

## Remaining limitations

- Third-party provenance/CVEs described above; no claim of production security acceptance.
- Versioning is not WORM Object Lock; privileged administrators can change raw objects.
  The ingestion adapter prevents overwrites and detects tampering by downloaded hashes.
- Single-client design serializes S3 publication under SQLite's writer lock; large-scale
  concurrency would need a separate transaction/outbox design outside this task.
- Legacy identities client01 are retained and remain subject to existing authentication
  policy. Credentials/ownership were not silently reassigned to collector01.
- Loopback HTTP is for local/internal communication; remote deployment still needs the
  existing HTTPS termination. No Windows Firewall settings were changed.
