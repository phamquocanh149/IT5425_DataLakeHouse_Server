# Phase 1 — Final verification and closeout

Date: 2026-11-22 (Asia/Saigon). **PARTIAL — do not merge yet.**

## Revision and scope

- Baseline: `69721c88b95a4158ebc3b1fae1cef312eba422a0`.
- Verified implementation: `291b81bbfbc8fa54a70cf9ced7cbb6aaef6a9499`.
- Branch: `phase1/final-verification`.
- Repository: `D:\Trực quan hóa\DataLake_Warehouse\climate-platform` (the parent is not a Git repository).
- Client in CI: `63a4773f501d5eb55be835d6852564bfd6fa0ebb`; local Client: `2b5b8accfe5c136a1c1f1e585b47c7567b6e5f94`.
- Audited the pre-existing uncommitted Phase 1 refactor, including new/untracked modules, against the baseline. No Phase 2, database/storage replacement, or scientific algorithm change.

## Findings corrected

1. `DATA_LAKE_DIR` no longer controlled Bronze/Silver after the refactor. Restore its fallback when `LOCAL_DATA_DIR` is absent. Explicit canonical roots, including default-valued `SCRATCH_DIR`, take precedence over legacy aliases. Four regression tests cover roots and worker identity.
2. Direct execution of GIS/recovery scripts lost the repository root on `sys.path`; `gis_smoke.py` reproduced `ModuleNotFoundError: scripts`. Restore that path only for scripts importing sibling operational scripts.
3. API Dockerfile omitted scripts required by Compose smoke. Restore `COPY scripts`. Include the package README in both Docker build contexts.
4. Cosmetic edits to the science worker changed its recipe SHA-256. Restore the exact baseline worker bytes, and adapt its console wrapper without editing the worker. Worker SHA-256: `10be63a92cf68819c79b58c93269ecd39d40f5324684ab82c9d40dd34c0b70ce`.
5. Move byte-preservation Git attributes with scientific resources, exclude the byte-pinned worker from formatting, and ignore packaging build outputs.
6. Add an isolated installed-wheel smoke command and run it in CI. Existing domain logic is retained.

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
| Standalone wheel | PASS | `$P -I scripts/package_smoke.py`: fresh temporary cwd/storage; asserts site-packages import, bundled cleaner/historical hashes, entry points, API readiness/upload/duplicate/checksum |
| Console commands | PASS | Installed `climate-usdm-worker.exe --help` and `climate-usdm-replay.exe --help` |
| API compatibility | PASS | Exact parsed OpenAPI equality against an archived baseline checkout; ingestion function/class AST unchanged after extraction |
| Scientific recipe compatibility | PASS (bytes) | Cleaner, historical recipe and current worker match baseline Git blobs byte-for-byte; this is not a substitute for real GIS execution |
| Local Client | PASS | `$P -m pytest ../climate-collector/tests -q`: **59 passed** |
| CI-pinned Client | PASS | Archive exact pinned commit to `.test-runs/client-pinned`, set `PYTHONPATH`/`CLIENT_REPO_PATH`; **59 Client tests + 7 real HTTP integration tests passed** |
| Portal | PASS, component scope | Full Server suite includes Portal policy, signed OIDC token validation, previews/downloads, history, hash checks and independent restore invalidating sessions. Installed-wheel Portal initialization and anonymous access rejection also pass. A standalone OIDC redirect attempt without an IdP returned 503; no end-to-end IdP/browser claim |
| Docker API | NOT VERIFIED on final image yet | First image built; final-source build in progress at this report revision |
| Docker GIS / Python 3.14 | NOT VERIFIED yet | `docker build -f Dockerfile.worker -t climate-phase1-worker:closeout .` in progress at this report revision |
| Compose / real MinIO | BLOCKED | `scripts/compose_smoke.py` executed and stopped at missing `MINIO_MC_DIGEST`; no real storage smoke ran |
| MinIO independent recovery | BLOCKED | `scripts/minio_recovery_smoke.py` executed and rejected missing verified `MINIO_DIGEST` |
| Git diff / secrets / runtime | PASS, bounded scan | `git diff --check`; candidate-file scan for private-key/token patterns, exact workstation `.env` secret values, runtime DB/archive paths: zero findings. No `.env`, runtime or build output staged |

## Isolation and remaining gates

- Tests used fresh temporary roots, fake credentials and the existing isolated fixtures. The original source data, local lake, SQLite databases, backups and Docker volumes were not deleted or migrated.
- Docker Desktop initially had no daemon; starting it made Linux Docker available. Build tags are unique to this verification. No existing deployment containers were intentionally changed.
- Official registry queries for `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` and `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` both returned **401 Unauthorized**. GitHub repository variables contain neither required digest. Existing third-party local images were not substituted.
- Real MinIO bucket/version/checksum, outage/retry, restart persistence and full-volume restore remain unverified until official digests and registry access are supplied. Image vulnerability scans/SBOMs are also outstanding.
- Browser UAT, production IdP/TLS, off-host recovery and production load are outside this local evidence. No production deployment was performed.
- Setuptools warned that the table form of `project.license` is deprecated; it did not fail the sdist/wheel build. FastAPI TestClient emitted an HTTPX deprecation warning.

## GitHub and merge decision

Implementation commit was pushed to the Phase 1 branch. Current run:
[Server checks 45035555960](https://github.com/phamquocanh149/IT5425_DataLakeHouse_Server/actions/runs/45035555960).
Its final result is pending at this report revision.

The baseline run failed at **Install Trivy**, with image scan/Compose/MinIO restore skipped. Historical GIS/build success is not counted as verification of this change.

The GitHub branch-protection endpoint returned 404 and the rulesets endpoint returned an empty list. Required branch-protection contexts therefore are **NOT VERIFIED**; a job's name alone does not establish enforcement. Before merge, confirm the exact final SHA has successful **Required real GIS and checkpoint restore** and **verify** jobs, including wheel, image scanning, Compose and independent MinIO restore. **Do not recommend merge or declare Phase 1 fully complete while these gates remain open.**
