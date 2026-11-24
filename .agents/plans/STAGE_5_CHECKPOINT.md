# Stage 5 — Checkpoint toàn pipeline và phục hồi

Nguồn chuẩn plan: [AGENT.md](AGENT.md). Rules/convention: [../../AGENTS.md](../../AGENTS.md).

**Trạng thái: PARTIAL, triển khai ngày 2026-11-22 theo scope người dùng giao.** Stage 5 thay
backlog đa nguồn/analytics bằng mục tiêu backup/restore đủ Bronze + registry + warehouse +
products + recipe và kiểm chứng release bằng lệnh local. Repo **không dùng CI/CD**; mọi gate
phải có bằng chứng chạy local (command/date/artifact). Không thay visualization/dashboard,
không thay upload contract/schema registry. Backlog đa nguồn/analytics trước đây chuyển sang công
việc sau Stage 5, chưa triển khai (xem [BACKLOG.md](BACKLOG.md)).

## 5.1 Task

| ID | Công việc | Trạng thái / bằng chứng |
|---|---|---|
| S5.01 | Checkpoint thống nhất và restore độc lập | DONE local: `scripts/backup/medallion_backup.py`; SQLite backup API, raw/products/history/recipe hashes, đối soát Gold CSV/warehouse; target mới, không ghi đè |
| S5.02 | Lưu recipe và kiểm chứng lịch sử | DONE cho build mới: `products/recipes/<sha256>.py`; thiếu recipe lịch sử thì fail-closed. Pilot Stage 3 hash `54054e45...` đã khôi phục bytes khớp SHA-256, lưu trong vendor/usdm/recipes |
| S5.03 | GIS bắt buộc chạy local | DONE local: `REQUIRE_GIS_TESTS=1` + JUnit zero skips; vendored cleaner có provenance/hash test. Không dùng CI/CD |
| S5.04 | Build/test/scan đúng API và worker release | DONE code: Dockerfile.worker, scan/SBOM bốn images theo image ID, Compose no-build, lưu tested image archive; Docker chưa chạy local |
| S5.05 | Real MinIO restore drill và version history | DONE automation: `scripts/smoke/minio_recovery_smoke.py`, all versions/delete markers, restore độc lập, readyz, HTTP DUPLICATE và replay; NEEDS VERIFICATION vì Docker engine unavailable |
| S5.06 | Off-host và RPO/RTO | PARTIAL: `scripts/backup/recovery_drill.py` đo data recovery/age/RPO khi có incident; chưa có đích off-host, chưa chứng minh service RTO <=2h/RPO <=24h |
| S5.07 | Tests và tài liệu | 130 Server + 59 Client tests PASS; Server gồm 5 GIS thật và 19 Stage 5 tests; Ruff PASS. Runbook `docs/STAGE5_PRODUCTION_READINESS.md` |

## 5.2 Bằng chứng

Drill thật local USDM tuần 2020-01-07: 1 observation/build, 3.259 Gold rows, 2 recipe files;
restore/đối soát 0,406 giây trên mẫu nhỏ, không phải service RTO hay benchmark tải. Artifacts:
`.test-runs/stage5-real-13ad1c10d67248a2a34292b731783dac` cùng sibling `-checkpoint`, `-restored`,
`-recovery.json`. GIS synthetic end-to-end có replay không trùng. Không sửa raw/source, không xóa
build pilot hay viết lại historical hashes.

Checkpoint đầy đủ lịch sử Stage 3 đã restore local: **130 observations, 131 builds, 426.929 Gold
rows lịch sử, 3 recipe files**. Current sau restore vẫn 423.670 rows, 0 mismatch/missing/extra;
source/product hashes khớp. Data recovery 31,39 giây. Artifact
`.test-runs/stage5-history-f4c2fbb8a9724bb9a3219938ae7076c6` và sibling `-restored`,
`-recovery.json`. Sau bổ sung lưu recipe qua restore → backup, chạy lại 19 tests Stage 5 PASS; full
suite trước đó 130 PASS. Xem `../../docs/STAGE5_RESULTS.json`.

## 5.3 Gate đóng Stage 5

Chạy local full suite với GIS không skip; scan/build đúng artifacts; real MinIO restore +
versions/delete markers + DUPLICATE đạt; off-host copy verify trên storage độc lập; đo service
RPO/RTO. Recipe pilot đã khôi phục đúng hash; không sửa lịch sử. Local PASS không thay các gate
này. Không có CI/CD hoặc branch protection để thay thế bằng chứng local.

## 5.4 Pristine deploy readiness (2026-11-23, chưa thực thi)

Rà soát tĩnh phát hiện rủi ro **clean clone → `docker compose up`** trên repo sạch, chưa được xác
minh và có thể thất bại. Đây là gate deployment, không phải bằng chứng đã deploy.

| ID | Rủi ro có căn cứ | Bằng chứng | Trạng thái |
|---|---|---|---|
| S5.08 | Image minh bạch không build được từ repo sạch | `pyproject.toml` khai báo package-data `datasets/usdm/resources/historical_recipes/*.py` nhưng chỉ có `resources/` và `resources/usdm_bronze_to_silver.py`; không có thư mục `historical_recipes/` (wheels bỏ qua pattern không khớp, không fail). Extra `portal` (`PyJWT`/`cryptography`) đã bỏ vì chuyển sang password auth. | NEEDS VERIFICATION — cần clean venv `pip install -e .[dev]` + `python -m build` + `pip check` |
| S5.09 | Compose không tự dựng được | `.env.example`, `compose.yaml` để trống `MINIO_DIGEST`/`MINIO_MC_DIGEST` có chủ đích; Compose yêu cầu artifacts được xác minh, không có bước `build` cho demo/source. Pristine repo thiếu `.env`. | NEEDS VERIFICATION — biến nền trường template + dùng image đã pin từ artifacts tin cậy |
| S5.10 | Import GIS lệch pin | `scripts/smoke/gis_smoke.py`, `scripts/release/check_gis_report.py`, `scripts/usdm/verify_usdm.py` dùng `pyproj.crs`/`transformer` trong khi `pyproject.toml` khai báo `pyproj==3.8.0` (API 3.x dùng `pyproj.CRS`/`pyproj.Transformer`), chưa chạy thực tế. | NEEDS VERIFICATION — chạy smoke GIS trong venv đúng pin; sửa import sau khi xác nhận |
| S5.11 | Chẩn đoán minh bạch | Môi trường local mặc định `requirements-dev.txt`/`requirements*.txt` thay vì cài từ `pyproject.toml`; verify cần chạy thử cả hai đường cài đặt. | TODO — ghi rõ "đường cài nào là canonical" trong rule và tài liệu local |

Các mục trên **chỉ chốt DONE khi** có báo cáo (command/date/env) từ môi trường sạch. Không suy
DONE từ việc repo cache/venv hiện có vẫn chạy được.

Xem runbook, lệnh và evidence: `../../docs/STAGE5_PRODUCTION_READINESS.md`.
