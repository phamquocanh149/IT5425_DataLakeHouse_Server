# Phase 1 — Final verification and closeout

Date: 2026-11-22 (Asia/Saigon). **PARTIAL — do not merge yet.**

## Revision and scope

- Baseline: `69721c88b95a4158ebc3b1fae1cef312eba422a0`.
- Verified implementation: `291b81bbfbc8fa54a70cf9ced7cbb6aaef6a9499`.
- Repair/documentation: `59c6d141e0d58f99cb77798651009c6f328abb63`.
- Branch: `phase1/final-verification`.
- Repository: `D:\Trực quan hóa\DataLake_Warehouse\climate-platform` (the parent is not a Git repository).
- Pinned Client: `63a4773f501d5eb55be835d6852564bfd6fa0ebb`; local Client: `2b5b8accfe5c136a1c1f1e585b47c7567b6e5f94`.
- Audited the pre-existing uncommitted Phase 1 refactor, including new/untracked modules, against the baseline. No Phase 2, database/storage replacement, or scientific algorithm change.

## Findings corrected

1. `DATA_LAKE_DIR` no longer controlled Bronze/Silver after the refactor. Restore its fallback when `LOCAL_DATA_DIR` is absent. Explicit canonical roots, including default-valued `SCRATCH_DIR`, take precedence over legacy aliases. Four regression tests cover roots and worker identity.
2. Direct execution of GIS/recovery scripts lost the repository root on `sys.path`; `gis_smoke.py` reproduced `ModuleNotFoundError: scripts`. Restore that path only for scripts importing sibling operational scripts.
3. API Dockerfile omitted scripts required by Compose smoke. Restore `COPY scripts`. Include the package README in both Docker build contexts.
4. Cosmetic edits to the science worker changed its recipe SHA-256. Restore the exact baseline worker bytes, and adapt its console wrapper without editing the worker. Worker SHA-256: `10be63a92cf68819c79b58c93269ecd39d40f5324684ab82c9d40dd34c0b70ce`.
5. Move byte-preservation Git attributes with scientific resources, exclude the byte-pinned worker from formatting, and ignore packaging build outputs.
6. Add an isolated installed-wheel smoke command and run it locally. Existing domain logic is retained.
7. The Trivy installer failed for `v0.68.2` because its official release asset was unavailable despite the Git tag existing. Pin `v0.76.2`, whose official release has Linux assets, without weakening any scan gate.

## Execution evidence

Commands below run from the repository. `$P` denotes `.test-runs/closeout-venv/Scripts/python.exe` (fresh Python 3.11.0 venv); `PYTHONUTF8=1` was set for Windows paths. Logs and XML are retained locally under ignored `.test-runs/closeout-*`, not committed as runtime data.

| Gate | Result | Command / evidence |
|---|---|---|
| Initial full Server suite | PASS with explicit GIS skips | `.venv/Scripts/python.exe -m pytest -q --junitxml=.test-runs/closeout-baseline.xml`: **125 passed, 5 skipped** |
| Final full Server suite | PASS with explicit GIS skips | `$P -m pytest -q --junitxml=.test-runs/closeout-final.xml`: **129 passed, 5 skipped**; includes API/TCP, Portal, registry, lineage, revisions, checksum, checkpoint, corruption and recovery tests |
| Ruff | PASS | `$P -m ruff check .`; `$P -m ruff format --check .`: 75 files formatted; scientific byte-pinned files intentionally excluded |
| Clean package install | PASS | `$P -m pip install '.[dev,portal]' build`; `$P -m pip check`: no broken requirements |
| Windows editable install | FAIL, tooling limitation | `$P -m pip install -e '.[dev,portal]' build`: setuptools `_encode_pth` uses cp1252 on Python 3.11 and cannot encode the Vietnamese checkout path; regular wheel installation succeeds |
| sdist and wheel | PASS | `$P -m build --outdir .test-runs/closeout-dist`; builds wheel from sdist; reinstall that wheel with `--no-deps --force-reinstall` |
| Standalone wheel | PASS | `$P -I scripts/smoke/package_smoke.py`: fresh temporary cwd/storage; asserts site-packages import, bundled cleaner/historical hashes, entry points, API readiness/upload/duplicate/checksum |
| Console commands | PASS | Installed `climate-usdm-worker.exe --help` and `climate-usdm-replay.exe --help` |
| API compatibility | PASS | Exact parsed OpenAPI equality against an archived baseline checkout; ingestion function/class AST unchanged after extraction |
| Scientific recipe compatibility | PASS (bytes) | Cleaner, historical recipe and current worker match baseline Git blobs byte-for-byte; this is not a substitute for real GIS execution |
| Local Client | PASS | `$P -m pytest ../climate-collector/tests -q`: **59 passed** |
| Pinned Client | PASS | Archive exact pinned commit to `.test-runs/client-pinned`, set `PYTHONPATH`/`CLIENT_REPO_PATH`; **59 Client tests + 7 real HTTP integration tests passed** |
| Portal | PASS, component and real local HTTP scope | Full suite covers policy, previews/downloads, history, hashes and independent restore invalidating sessions. `$P -I .test-runs/portal_tcp_smoke.py` passed installed-wheel HTTP discovery, PKCE/RSA callback, session and granted dataset access with a fresh synthetic release and local demo IdP. An initial attempt without a running IdP returned 503; the subsequent complete loopback flow passed. Browser/production IdP UAT is not claimed |
| Docker API | PASS | `docker build -t climate-phase1-api:closeout .`; `$P .test-runs/docker_api_smoke.py`: real TCP readiness/upload/duplicate/checksum. `docker run --rm --tmpfs /app/src climate-phase1-api:closeout python -I /app/scripts/smoke/package_smoke.py`: PASS with source tree masked |
| Docker GIS / Python 3.14 | PASS locally | `docker build -f Dockerfile.worker -t climate-phase1-worker:closeout .`; image Python **3.14.10**; container `pytest tests/usdm/test_usdm_gis.py` with `REQUIRE_GIS_TESTS=1`: **5 passed, zero skipped**. |
| Real GIS checkpoint / independent restore | PASS | `docker run --rm --tmpfs /app/src climate-phase1-worker:closeout python /app/scripts/smoke/gis_smoke.py`: source tree masked; restored 1 observation, 1 build, 2 Gold rows and 2 recipe files; replay skipped 1, failed 0 |
| Baseline → installed refactor replay | PASS | `$P .test-runs/baseline_replay.py`: canonical `69721c8` processes one real source week into a new volume; refactor reports **0 succeeded, 1 skipped, 0 failed**, preserving build identity. See fixture caveat below |
| Full real USDM replay and scientific comparison | PASS | `$P .test-runs/gis_image_verify.py`: read-only source mount, new volume; **130 succeeded, 0 failed**; rerun **130 skipped, 0 failed**. `scripts/usdm/verify_usdm.py`: **130 weeks, 625 Silver features, 61 repairs, 423,670 matched Gold cells, 0 mismatched/missing/extra**, all source/product hashes verified |
| Compose / real MinIO | BLOCKED | `scripts/smoke/compose_smoke.py` executed and stopped at missing `MINIO_MC_DIGEST`; no real storage smoke ran |
| MinIO independent recovery | BLOCKED | `scripts/smoke/minio_recovery_smoke.py` executed and rejected missing verified `MINIO_DIGEST` |
| Git diff / secrets / runtime | PASS, bounded scan | `git diff --check`; candidate-file scan for private-key/token patterns, exact workstation `.env` secret values, runtime DB/archive paths: zero findings. No `.env`, runtime or build output staged |

## Isolation and remaining gates

Artifacts already verified: wheel SHA-256 `485137a096c0760a64e43f40e019d035a064eeed86bebdda1ea7c4cc4e361b6f`; API image ID `sha256:56598109c78c648e3232b2a3f7d6dc0ccadbb0ef2dfc7c89112070d8a1a7e2be`. Image/package runtime code corresponds to implementation SHA `291b81b`; later changes so far are documentation only.
GIS image ID: `sha256:48f9ccf75fab85e10f74c4e1ce3fd5512f42e09008847dae6eb9af4b636c5ac2`.
Retained isolated volumes: `phase1-usdm-8635ceaa78` (full replay), `phase1-baseline-a53c29bbf3` (canonical baseline compatibility), and `phase1-baseline-1271a5d480` (initial CRLF fixture investigation). No volume or backup was deleted.

The replay runner executes these commands inside the worker image, with `/source` mounted read-only from `D:\Trực quan hóa\data_crawl_USDM`, a new volume at `/storage`, `BASE_DIR=/storage`, `STORAGE_BACKEND=local`, and test-only keys:

```sh
python scripts/usdm/run_usdm.py --source-root /source --output-root /storage/products --gis-python /usr/local/bin/python
# Repeat the same command to verify idempotency, then:
python scripts/usdm/verify_usdm.py --source-root /source --output-root /storage/products --registry /storage/metadata/ingestion.sqlite3
```

Local evidence: `closeout-real-replay.log`, `closeout-real-replay-rerun.log`, `closeout-real-replay-verify.log`, `closeout-gis-image.xml`, `closeout-gis-image-restore.log`, and `closeout-baseline-replay.json` under `.test-runs/`. Runtime dependency versions are recorded in `closeout-packages.json`. Final Ruff check/format and `git diff --check` passed after report updates.

The first baseline replay harness failed its skip assertion because Windows `git archive` applied CRLF conversion to the old worker (`877fabdc...`), unlike the canonical Git blob (`10be63a9...`). Confirmed that the only byte difference was CRLF and restored the **test fixture only** using `git show 69721c8:server/usdm_worker.py`. The fresh canonical-baseline run then passed. Read-only inspection of the documented existing local historical warehouse confirmed worker hashes `10be63a9...` and the preserved pilot `54054e45...`; no historical data was rewritten. Deployments using genuinely different worker bytes/library versions legitimately get a new recipe/build rather than silently reusing a different recipe.

- Tests used fresh temporary roots, fake credentials and the existing isolated fixtures. The original source data, local lake, SQLite databases, backups and Docker volumes were not deleted or migrated.
- Docker Desktop initially had no daemon; starting it made Linux Docker available. Build tags are unique to this verification. No existing deployment containers were intentionally changed.
- Official registry queries for `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` and `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` both returned **401 Unauthorized**. The required digest values were not available. Existing third-party local images were not substituted.
- The user confirmed they do not have these digests. MinIO's [official source-only distribution guidance](https://github.com/minio/minio#source-only-distribution) means availability of old binary images cannot be assumed. A source-built image would require a separately reviewed provenance policy; no such substitution was made here.
- Real MinIO bucket/version/checksum, outage/retry, restart persistence and full-volume restore remain unverified until official digests and registry access are supplied. Image vulnerability scans/SBOMs are also outstanding.
- Browser UAT, production IdP/TLS, off-host recovery and production load are outside this local evidence. No production deployment was performed.
- Setuptools warned that the table form of `project.license` is deprecated; it did not fail the sdist/wheel build. FastAPI TestClient emitted an HTTPX deprecation warning.

## Merge decision

Local verification remains partial: Docker builds/scans and real MinIO recovery are still
blocked by missing verified image digests and storage access. Do not declare Phase 1 fully
complete while these local gates remain open.
