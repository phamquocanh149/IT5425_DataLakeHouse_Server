# Stage 5 — Complete checkpoints and local release validation

Updated 2026-11-22 (Asia/Saigon). Scope: data recovery and release validation;
visualization/dashboard changes are excluded. Status: implemented and verified locally;
Docker/off-host/service recovery acceptance remains pending. This project does not use
CI/CD; every check must run locally and record its command, date and artifacts.

## Checkpoint contract

`scripts/backup/medallion_backup.py` supplements the Stage 2 Bronze-only tool. Use the Stage 5
tool for a deployment with USDM products. It never deletes source data or overwrites
an existing checkpoint/restore root. A failed run leaves an incomplete directory;
without a valid manifest/checksum it is not an accepted backup.

Supported layout under the explicit `--root`:

```text
metadata/ingestion.sqlite3
metadata/access.sqlite3       # required for S3; absent in offline local replay is recorded
data_lake/bronze/              # local raw, including retained unreferenced blobs
products/warehouse.sqlite3
products/{silver,gold,quality,reference}/...
products/recipes/<sha256>.py   # automatically retained by new pipeline runs
```

Custom metadata/product paths must first be mapped to this layout in an isolated
helper mount namespace; do not move live data to fit the tool. Absolute/escaping raw
paths, symlinks, junctions and hardlinks are rejected. This tool does not include the
Portal control DB, Client queues, TLS secrets or organization configuration. Those
have separate owners/runbooks. Portal serving copies are not the authoritative products.

The checkpoint stores consistent SQLite backups (including committed WAL), every
historical product/build, exact cleaner/worker bytes, grid snapshots, library versions
in build manifests, image references, and full stopped MinIO data when using S3.
Verification checks all observations, build identity/lineage, product hashes, each
Gold CSV against warehouse rows, and recipe hashes. It does not silently select only
current builds or discard pilot history. Raw remains immutable; no reprocessing during restore.

Pause **all** writers: Client/producers, ingestion API, pipeline runners, maintenance,
and other users of the MinIO instance. The OS pipeline lock additionally prevents a
concurrent USDM runner, but cannot stop arbitrary external writers. The CLI acknowledgement
is an operator assertion, not automatic proof of service shutdown.

## Local checkpoint and restore

From the Server repository; use NEW paths outside the source root. `--image` should
record the actual immutable image IDs/digests from the accepted release manifest.
The example placeholders below must be replaced, not passed literally.

```powershell
.venv/Scripts/python.exe scripts/backup/medallion_backup.py create `
  --root <runtime-root> --bundle <new-checkpoint> --writers-stopped `
  --image <api-image-id> --image <worker-image-id>
.venv/Scripts/python.exe scripts/backup/medallion_backup.py verify --bundle <new-checkpoint>
.venv/Scripts/python.exe scripts/backup/recovery_drill.py `
  --bundle <new-checkpoint> --target <new-restored-root> --report <new-report.json>
```

Keep the complete checkpoint directory together, including `manifest.json`,
`manifest.sha256` and `payload`. Image references are provenance, not embedded image
layers: retain the tested OCI/Docker image archives with the disaster recovery release
outside the host as well. Hashes detect corruption; protect write access to backups.

For old builds, repeat `--recipe <exact-old-cleaner-or-worker.py>` as needed. The file
must match the hash already in the historical manifest. No reconstructed or renamed
file is accepted unless its bytes match. Missing recipes cause failure before a complete
manifest is published. Do not rewrite historical build IDs/hashes to bypass this gate.

Legacy checkpoint `.test-runs/usdm-stage3` includes a pilot worker hash
`54054e45f09b47c82d50f91e6f2f870c60f32b98f0053d9f10b12597c1a49cfa`. Stage 5 recovered
the exact pre-library-version-recording worker bytes and verified them against that
trusted historical SHA-256. They are retained in `vendor/usdm/recipes/<hash>.py`, with
provenance; this file is not selected as the current worker. The current worker matches
`10be63a92cf68819c79b58c93269ecd39d40f5324684ab82c9d40dd34c0b70ce`.
Supply the historical worker, current worker and source cleaner using three `--recipe`
arguments when backing up this older runtime for the first time. Restored roots retain
all of them under `recipes/`, which subsequent checkpoints discover automatically.
No historical build IDs, hashes, pilot records or source data were changed.

## S3 / MinIO checkpoint and restore

Use a separate backup identity via the standard AWS credential chain (environment or
profile). Never broaden the ingestion identity into an administrator for backup.
Set `S3_BACKUP_ENDPOINT` explicitly for each source/restored instance. The identity
must enumerate buckets/versions and read every version in the instance being backed
up; it needs `GetObjectVersion`, including older versions. Use trusted isolated network
or TLS. Credentials are not written into the checkpoint.

1. Pause every writer, leave MinIO running temporarily. Capture **all** bucket versions
   and delete markers; the command streams/hash-checks every object version:

   ```powershell
   .venv/Scripts/python.exe scripts/backup/medallion_backup.py capture-s3 `
     --writers-stopped --s3-inventory <new-versions.json>
   ```

2. Stop MinIO cleanly. Keep writers stopped. In an isolated helper mount metadata,
   products and legacy Bronze under `<runtime-root>`, and the whole MinIO data volume
   separately at `<stopped-minio-root>`. Use the recorded release image. For Linux
   full-volume backup/restore, run the helper with sufficient rights to preserve numeric
   UID/GID and modes. This is not a reason to run the API as root.

   ```powershell
   .venv/Scripts/python.exe scripts/backup/medallion_backup.py create `
     --root <runtime-root> --bundle <new-checkpoint> --writers-stopped `
     --minio <stopped-minio-root> --s3-inventory <new-versions.json> `
     --image <api-image-id> --image <worker-image-id> --image <minio-digest>
   ```

3. Copy the complete bundle to the approved off-host destination. Run `verify` there
   or against its mounted copy. A second folder on this computer is **not** off-host.
   Retain an infrastructure/operator record identifying the separate storage location.
   Only resume the source deployment after the off-host copy has verified.
4. Restore to a NEW independent root/volumes using `scripts/backup/recovery_drill.py`. Optionally pass
   `--verified-copy <mounted-offhost-checkpoint>`; it checks that the copy is the same
   checkpoint and restores from that copy. No automatic overwrite or production switch.
5. Start a separate MinIO instance using `<restored-root>/minio`, the same verified
   MinIO release and required secrets/KMS configuration. Set `S3_BACKUP_ENDPOINT` to
   that restored instance, then run:

   ```powershell
   .venv/Scripts/python.exe scripts/backup/medallion_backup.py reconcile `
     --root <restored-root> --live-s3
   ```

   This verifies object bytes, every captured historical version/delete marker, registry,
   products, recipes and warehouse. Offline verification explicitly reports the number
   of S3 objects still awaiting live verification. Do not treat it as live acceptance.
6. Start the isolated API with its restored metadata/data mounts and non-root ownership;
   check `/readyz`. Re-upload an observation under the original identity and expect
   `DUPLICATE` with the same file_id/revision. Rerun processing and verify no new rows/builds.
   Preserve the ready/duplicate/live-reconciliation results in the drill report.

The full-volume method covers the current single-node Compose deployment. It does not
claim a coordinated backup of a distributed MinIO cluster across multiple hosts.
Never initialize a new bucket layout over an existing restored volume to hide failures.

## Recovery metrics and recurring operation

`scripts/backup/recovery_drill.py` records checkpoint identity, UTC start/end, measured data restore
duration, counts and verified-copy status. `--incident-at <timezone-aware-ISO-time>`
enables actual checkpoint-age RPO calculation; without an incident it reports age,
not an invented incident RPO. Future/earlier-than-checkpoint incident values must not
be used as operational evidence. A same-host drill does not certify off-host durability.

Initial targets remain RPO <=24h and **service** RTO <=2h. Data copy/reconciliation time
alone is not service RTO: measure from recovery initiation through live MinIO checks,
API readiness and the successful duplicate upload. Record operator, host/storage,
checkpoint, image IDs, actual timestamps and all failure/retry time. Keep production
acceptance pending until this full sequence has passed on the target infrastructure.

Schedule a verified off-host checkpoint daily, alert if its age exceeds 24h, and perform
a restore drill monthly and after storage/schema/release changes. Scheduler credentials,
off-host destination and maintenance windows have not been supplied, so no unattended
production service/job has been installed by this change.

## Local release validation

There is no CI/CD pipeline. Run this validation locally before accepting a release:

- Record the exact Client checkout used with Server regression; never silently use an
  arbitrary HEAD. Update the reviewed commit deliberately with Server/Client regression.
- Python 3.11 API tests and Python 3.14 GIS environment are separate. GIS dependencies
  are pinned in `requirements-gis.txt`. Missing GIS causes failure in required mode;
  `scripts/release/check_gis_report.py` also rejects empty/failed/skipped GIS suites.
- Vendored source cleaner is byte-pinned with `vendor/usdm/PROVENANCE.json` and a test.
  Original source repository remains read-only. When a source checkout supplies its
  own cleaner, the pipeline keeps existing behavior and records that exact hash.
- Real GIS synthetic end-to-end test exercises pipeline, checkpoint, independent
  restore and idempotent rerun. `Dockerfile.worker` supplies a separately packaged worker.
- Build API/worker images, run GIS/restore inside the actual worker image, and scan
  API/worker/MinIO/mc with Trivy. HIGH/CRITICAL findings or missing images/tools fail.
  Each image gets a CycloneDX SBOM and immutable image ID in the scan manifest.
- Compose smoke consumes the scanned API image with `--no-build`. A separate
  `scripts/smoke/minio_recovery_smoke.py` seeds real GIS data into real MinIO, retains old versions
  and a delete marker, snapshots stopped storage, restores to an independent tree,
  verifies every version, starts the API and checks HTTP DUPLICATE plus pipeline replay.
  It uses synthetic data, unique containers/network/volume, no host ports, and test-only
  admin credentials. It does not certify production least-privilege policy or off-host DR.
- Only after all gates pass, preserve the exact API/worker image archive and checksum,
  Server/Client commits and scan manifest. Deploy those artifacts; do not rebuild a
  different image and assume the prior tests/scan cover it. Local artifact retention is
  an operator decision, not a substitute for the long-term disaster recovery archive.

Set `MINIO_IMAGE`/`MINIO_MC_IMAGE` in the local environment to the digest-pinned
source-built MinIO and mc images before Compose smoke. No hosted workflow or
branch-protection setting is used; do not add CI/CD. Publishing/deployment is not
automated or authorized by this change.

Local commands when dependencies are already available:

```powershell
$env:REQUIRE_GIS_TESTS='1'
$env:USDM_GIS_PYTHON='E:/anaconda/python.exe'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/smoke/gis_smoke.py --gis-python $env:USDM_GIS_PYTHON
.venv/Scripts/python.exe -m ruff check --no-cache .
.venv/Scripts/python.exe -m ruff format --check --no-cache .
# Docker Linux and exact images must be available for these commands:
$env:MINIO_IMAGE='noname12346767/my-minio@sha256:<64 hex>'
$env:MINIO_MC_IMAGE='noname12346767/mc-allos@sha256:<64 hex>'
.venv/Scripts/python.exe scripts/release/verify_images.py --api-image <api-image> --worker-image <worker-image>
$env:CLIMATE_API_IMAGE='<api-image>'
$env:CLIMATE_WORKER_IMAGE='<worker-image>'
.venv/Scripts/python.exe scripts/smoke/minio_recovery_smoke.py
```

## Evidence and remaining gates (2026-11-22)

Machine-readable evidence: [STAGE5_RESULTS.json](STAGE5_RESULTS.json).

- Full Server suite: **130 passed**, including 5 real GIS tests and 19 new Stage 5 tests;
  one existing Starlette/httpx deprecation warning. No GIS skips in this run.
- Client regression: **59 passed**; Ruff check/format PASS. No CI/CD was used.
- Real GIS synthetic pipeline/checkpoint/restore/rerun: PASS, 1 observation/build,
  2 Gold rows, no duplicate build after restore.
- Real USDM source week 2020-01-07, isolated new runtime: PASS, 1 observation/build,
  **3,259 Gold rows**, 2 archived recipes. Local data restore/verification measured
  **0.406 seconds** on this tiny sample; not service RTO or a capacity result.
  Runtime `.test-runs/stage5-real-13ad1c10d67248a2a34292b731783dac`, sibling
  `-checkpoint`, `-restored`, `-recovery.json`. Original source data untouched.
- Full original Stage 3 history checkpoint/restore: **130 observations, 131 builds,
  426,929 historical Gold rows, 3 exact recipe files**. Current after restore: 130 weeks,
  625 Silver features, 61 repairs, **423,670 matched Gold rows**, 0 mismatch/missing/extra;
  source/product hashes verified. Measured local data recovery **31.39 seconds**.
  Checkpoint `.test-runs/stage5-history-f4c2fbb8a9724bb9a3219938ae7076c6`, sibling
  `-restored` and `-recovery.json`. No source/history mutation. This is same-host data
  recovery, not service RTO or off-host acceptance.
- After recipe recovery and preserving archived recipes across restore -> backup,
  all **19 Stage 5 tests passed again (5.48s)**; the full 130-test run above preceded
  this narrowly tested follow-up.
- Docker engine unavailable locally; new Docker builds, scans and real MinIO drill have
  **not** been executed/accepted in this session. No CI/CD exists to run them.
- Off-host destination and actual incident/service RPO/RTO acceptance pending.
- Exact pilot recipe recovered and authenticated by its original SHA-256; see above.

Stage 5 is **PARTIAL** until these external gates are closed. Local unit tests,
fake S3 tests and the synthetic GIS drill are reported separately from real MinIO evidence.
