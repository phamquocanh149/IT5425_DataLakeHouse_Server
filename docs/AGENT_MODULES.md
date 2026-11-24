# Server — hướng dẫn module, Stage 3 USDM và Stage 4 Portal

Hướng dẫn chung, contract Stage 1–2 và lịch sử nghiệm thu nằm ở
[../AGENT.md](../AGENT.md). File này bổ sung chi tiết implementation Server;
không thay thế hoặc nâng trạng thái các gate MinIO/deployment chưa nghiệm thu.

## Phase 1 — Refactor modular monolith (2026-11-22)

Toàn bộ backend Python nay nằm trong package cài đặt được `src/climate_platform/`
(không còn `server/`, không còn compatibility shim). Ánh xạ module cũ → mới:

| Cũ (`server/`) | Mới (`src/climate_platform/`) |
|---|---|
| `main.py` | `api/app.py` |
| `access.py`, `security.py` | `api/access.py`, `api/security.py` |
| `portal/*` | `api/portal/*` |
| `ingestion.py` | `ingestion/service.py` (+ `ingestion/validation.py`) |
| `metadata.py` | `catalog/repository.py` |
| `maintenance.py`, `s3_maintenance.py` | `catalog/maintenance.py`, `catalog/s3_maintenance.py` |
| `storage.py` | `infrastructure/object_store.py` |
| `readiness.py` | `infrastructure/readiness.py` |
| `usdm.py` | `datasets/usdm/processor.py` (+ `UsdmProcessor` strategy) |
| `usdm_worker.py` | `datasets/usdm/science.py` |
| `vendor/usdm/*` | `datasets/usdm/resources/*` (byte-pinned) |

Thêm `processing/{contracts,engine,publisher}.py` (DatasetProcessor strategy + registry,
publish helper) và `cli.py` (console entry points). `config.py` tập trung mọi Settings.
Logic khoa học, chữ ký checksum, revision, lineage và output Bronze/Silver/Gold USDM
giữ nguyên; toàn bộ 130 tests không đổi hành vi. Chi tiết/trạng thái gate xem
Phase 1 trong [../AGENT.md](../AGENT.md).

## Stage 4 — Data Portal: Implemented local, Pending UAT

Ngày 2026-11-22: Mốc A đã được người dùng duyệt, Mốc B đã triển khai và demo bằng
USDM Stage 3. Demo dùng tài khoản/mật khẩu cục bộ. Xem
[runbook/kết quả](../docs/STAGE4_IMPLEMENTATION.md), [API](../docs/STAGE4_API_CONTRACT.md),
[Checklist](../docs/STAGE4_ACCEPTANCE.md). **Chưa đánh dấu Completed; chờ UAT.**

Implementation: `portal/` mở rộng FastAPI qua `install_portal`, opt-in
`PORTAL_ENABLED` trong main; React/TypeScript ở `../frontend-climate-platform/`; username/password session,
Viewer/Operator/Admin và grants dataset/layer/action kiểm tra mỗi request.
`data_lake/portal/releases/usdm-stage3-v1` riêng ngoài `.test-runs`, current/history
pin xuyên preview/download. 130 current tuần, 131 historical builds, 423.670 Gold rows.
`reader/read_worker` tách đọc JSON/SQLite vào subprocess, cap 256 MiB và timeout;
`prepare_gis` chỉ chạy offline, không thêm GIS vào API process.
Giữ ingestion/auth collector/ownership và schema Stage 1–3. Chỉ xem/tải dữ liệu;
không upload UI, pipeline/collector control, SQL tự do hay Silver/Gold MinIO.
API/security, browser E2E và hồi quy đã chạy local; restore thật sang root độc lập
đã verify. Không đồng nghĩa production TLS, load SLO hoặc MinIO đã nghiệm thu.
Scripts: `scripts/portal/prepare_portal.py`, `scripts/portal/run_portal_demo.py`,
`scripts/backup/portal_backup.py`;
tests: `tests/portal/test_portal.py`, `../frontend-climate-platform/tests/portal.spec.ts`.

## Phạm vi Stage 3 được giao ngày 2026-11-21

Tích hợp historical USDM M/CONUS qua Bronze → Silver → Gold, chạy offline theo batch.
Không thêm upstream downloader vào Server. Không thay API upload, registry schema,
ownership, revision semantics hoặc dependency runtime của FastAPI.

- `datasets/usdm/processor.py`: điều phối replay, snapshot shapefile sidecars thành ZIP
  xác định, gọi `MetadataManager.register_upload`, đọc lại Bronze và kiểm tra SHA-256,
  gọi GIS worker, publish sản phẩm bất biến và commit warehouse SQLite.
- `datasets/usdm/science.py`: worker Python riêng, tải bộ xử lý có sẵn từ
  `data_crawl_USDM/silver/scripts/usdm_bronze_to_silver.py` (fallback bản byte-pinned trong
  `datasets/usdm/resources/`) qua bản sao tạm.
  Bổ sung gate DM nguyên 0–4, CRS bắt buộc, geometry polygon hợp lệ, không bỏ
  feature âm thầm. Chạy cleaner theo từng tuần; không dùng `run()` nguồn vì
  nhánh skip của nó có thể tạo consolidated dataset thiếu các tuần đã tồn tại.
- Gold dùng tọa độ grid/lon/lat từ CSV tham chiếu, không dùng nhãn drought làm
  đầu vào. Point-in-polygon `within`, lấy max DM khi chồng lấn; ngoài đa giác
  là `0`, phân biệt với `D0`. Đây là mart centroid, không phải diện tích hạn hán.
- `scripts/process_data/usdm/run_usdm.py`: CLI offline có quyền của operator, không phải API
  collector. Owner cố định `usdm-replay`, dataset key `usdm/gis/CONUS/M/weekly`.
- `scripts/process_data/usdm/verify_usdm.py`: kiểm tra source/output hashes và đối chiếu Gold,
  chỉ chọn build mới nhất của observation VERIFIED/current theo registry.

## Lưu trữ và retry

Bronze tái sử dụng backend cấu hình hiện hữu; ZIP là transport container, từng
sidecar giữ nguyên bytes và có hash trong lineage. Không gọi đây là ZIP gốc của upstream.
Silver GeoParquet, Gold CSV, quality JSON và snapshot grid lưu trên filesystem local
dưới output root; warehouse là `warehouse.sqlite3`, không đặt lên S3/network filesystem.
S3 Bronze có đường đọc theo VersionId khi có; Silver/Gold S3 chưa triển khai.

Build identity gồm file_id/raw hash, hash cleaner/worker, grid hash và phiên bản
thư viện GIS. Các product có đường dẫn theo source/week/build/content hash.
`builds`, `gold_cells`, `gold_weekly` giữ lịch sử; không tổng hợp mọi build thành
current. Phải join registry current và chọn recipe/build mới nhất như runbook.

OS file lock tuần tự hóa các runner cùng output root và tự nhả khi tiến trình chết.
SQLite transaction chỉ bao quanh publish metadata/Gold rows, không bao quanh GIS/S3.
Lỗi giữ nguyên Bronze, ghi attempts và không commit build thiếu. Retry kiểm tra hash
trước skip; artifact lỗi yêu cầu reconciliation, không tự ghi đè. Orphan do crash trước
commit có thể được nhận lại. Không tự xóa orphan. Snapshot registry/products trước
thao tác vận hành; runbook Stage 2 chưa tự backup warehouse mới này.

## Kiểm chứng

2026-11-21: full local replay 130/130 tuần; rerun 130 skipped, 0 failed. Silver 625
feature/61 repairs; Gold 423.670 dòng khớp tham chiếu 100%; source/product hashes PASS.
Full suite có GIS: 81 passed; Ruff check/format PASS. Regression Stage 1–2 giữ nguyên.

Xem [USDM_STAGE3.md](../docs/USDM_STAGE3.md) cho lệnh, schema, kết quả dữ liệu thật
và giới hạn. Test orchestration dùng fake worker phải báo riêng với test GIS thật.
GIS tests opt-in qua `USDM_GIS_PYTHON` và `USDM_SOURCE_ROOT`; không cài GIS vào API
chỉ để collection test. Dữ liệu nguồn chỉ đọc; mọi output/test phải ở workspace Server.

## Stage 5 — Checkpoint và phục hồi (2026-11-22)

`usdm.py` lưu cleaner/worker đúng bytes vào `products/recipes/<sha256>.py` trước
build; source cleaner vẫn ưu tiên khi có, fallback bản byte-pinned trong `vendor/usdm`.
Không đổi build identity, raw hoặc output khoa học. GIS worker image tách API image.
Checkpoint/restore nằm ở `scripts/backup/medallion_backup.py`, đo recovery ở
`scripts/backup/recovery_drill.py`.
Thiếu historical recipe phải báo lỗi, không sửa hash/build cũ để vượt gate.
Gate local bắt buộc real GIS, scan bốn image và test đúng release artifacts; repo không dùng CI/CD.
Full-volume MinIO drill là test cô lập; chưa chạy local vì thiếu Docker engine.
Xem [Stage 5](../docs/STAGE5_PRODUCTION_READINESS.md); trạng thái PARTIAL cho
production/off-host, dù full 130 tests local PASS. Recipe pilot cũ đã
khôi phục đúng SHA-256 và được lưu trong vendor/usdm/recipes; không dùng làm worker hiện tại.
