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

## Refactor — kiến trúc module kiểu NestJS (2026-11-24)

Chuyển từ chia theo layer sang **feature modules**: mỗi bounded context là
`modules/<feature>/` gồm `controller` (route) · `service` (nghiệp vụ) · `repositories/`
(truy cập dữ liệu) · `dto` (schema) · `guards`. Composition root ở `app.py` (AppModule);
`config.py` giữ nguyên (ConfigModule). Không đổi hành vi HTTP/schema/hash/revision/object-key.

**Controller mỏng (mục 13 REFACTOR.MD):** controller chỉ nhận request → gọi **service** → dựng
response; business logic/ORM/transaction/audit nằm ở `service` (service là nơi xử lý logic đầu
tiên). Service không import FastAPI/Starlette request (controller truyền `common.pipes.RequestContext`).

| Trước (`src/climate_platform/`) | Sau (`src/climate_platform/`) |
|---|---|
| `api/app.py` | `app.py` (AppModule, uvicorn target) |
| `api/access.py` (`authenticate`) | `modules/auth/services/api_key.py` |
| `api/access.py` (middleware + accounting) | `common/middleware.py` |
| `api/security.py` | `modules/auth/guards.py` + `modules/authorization/` |
| `infrastructure/readiness.py` | `modules/system/readiness.py` |
| `infrastructure/object_store.py` | `s3/minio_repository.py` + `s3/keys.py` (cấp package) |
| `ingestion/*` | `modules/ingestion/*` |
| `catalog/repository.py` (SQL) | `repositories/catalog_repository.py` (SQLAlchemy) + entity `entity/registry.py` |
| `catalog/repository.py` (`FileMetadata`, `file_hash`) | `entity/view.py` + `common/hashing.py` |
| `catalog/repository.py::_register_s3` | `modules/catalog/service.py` |
| `catalog/{maintenance,s3_maintenance}.py` | `modules/catalog/*` |
| `processing/*` | `modules/processing/*` |
| `api/portal/auth.py` | `modules/auth/controllers/{login,session}.py` |
| `api/portal/{store,releases}.py` | `repositories/control_repository.py` + `repositories/releases.py` (cấp package) |
| `api/portal/api.py` (926 dòng) | `modules/portal/controllers/{catalog,selection,admin}.py` + `services/*` |
| `api/portal/{reader,read_worker,prepare_gis,demo}.py` | `modules/portal/workers/*` |
| `api/portal/{app,config}.py` | `modules/portal/{module,config}.py` |
| `datasets/usdm/*` | không đổi (plugin, byte-pinned) |

Guard: xác thực ở `modules/auth/guards.py`; phân quyền (role/grant/source) ở
`modules/authorization/guards/`, export qua `modules/authorization/module.py`.
Gate/phase chi tiết: [plans/REFACTOR.MD](plans/REFACTOR.MD).

**Dọn vi phạm phân tầng (2026-11-24, mục 14 plan):** helper dùng chung (`file_hash`, `contained`,
PBKDF2 password) và domain error `PortalError` nay ở `common/`; `prepare_release` dời sang
`modules/portal/services/publish.py` (nên `repositories/releases.py` chỉ còn release artifact
store); `FileMetadata` ở `entity/view.py` (xoá `modules/catalog/model.py`); factory S3 client ở
`s3/client.py` dùng chung cho repo + readiness. `repositories/` và `s3/` **không** còn import
`modules.*`. Không đổi hành vi HTTP/schema.

## Refactor — Medallion layering Bronze→Silver→Gold (2026-11-24)

Tách xử lý pipeline khỏi `scripts/process_data/*` thành các tầng **một-trách-nhiệm** trong
package cài được; scripts chỉ còn entrypoint mỏng (tham khảo). Chi tiết + bằng chứng:
[plans/REFACTOR.MD §15](plans/REFACTOR.MD).

- **`src/climate_platform/medallion/`** (dùng chung): `contracts` (Layer/Readiness/StageResult/
  RunReport + Protocol Stage/Gate) · `paths` (root theo source+layer) · `io` (file_hash/
  write_json_atomic) · `lock` (exclusive_run — một bản) · `publisher` (publish_atomic/product_path)
  · `gate` (AllOf) · `runner` (MedallionRunner).
- **`datasets/<source>/`** mỗi file một việc:
  - `noaa/`: spec · paths · validation · bronze · gate · silver · gold · pipeline · runner_cli · processor
  - `usgs/`: bronze · paths · config · errors · store · validate · export · preprocess · daily · grid_huc ·
    manifest · method · silver · weekly · aggregate · gold · gold_validate · gate · pipeline · runner_cli · stage_cli · processor
  - `nldas/`: spec · paths · deps · bronze · references · partition · complete · gate · silver · gold ·
    pipeline · cli · runner_cli · processor
  - `usdm/`: bronze · worker · publisher · recipe · warehouse · pipeline · processor (+ `science.py`, `resources/` byte-pinned)
- `modules/processing/contracts.DatasetProcessor.discover()` trả `Readiness`; `publisher.py` re-export
  `medallion.publisher`; `default_registry` đăng ký `usdm/noaa/usgs/nldas`.
- Adapter `datasets/*/processor.py` **không còn** `sys.path.insert` vào `scripts/` — package sở hữu
  logic. Checkpoint sqlite cục bộ của USGS/NLDAS giữ sqlite3 (ngoại lệ có comment: store tiến trình,
  không phải registry/warehouse nền tảng).
- **USGS Bronze đến từ Client.** Server không crawl upstream: `datasets/usgs/` chỉ đọc Bronze do
  Client cung cấp (`bronze.py` giữ schema Parquet chuẩn hoá; `store.py` đọc `checkpoint.sqlite`;
  `validate.py`/`gate.py` đánh giá đủ điều kiện trên Bronze đó). Crawler chỉ còn là tham khảo ở
  `scripts/process_data/usgs/crawl_usgs.py` (CLI `run_usgs.py`), cùng mẫu với
  `scripts/process_data/noaa/crawl_noaa_cpc.py`. Bốn nguồn `usdm/noaa/usgs/nldas` đều theo luồng
  lấy dữ liệu từ Client; nguồn nào không có crawler tham khảo thì giữ nguyên.
- Thuật toán science/hash/revision/lineage/object-key/HTTP contract không đổi; `usdm/science.py` +
  `usdm/resources/` byte-pinned không format/lint.

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

## Stage 3 — mở rộng nguồn NOAA/USGS (2026-11-24)

Thêm hai nguồn ngoài USDM vào tầng xử lý Bronze → Silver → Gold và cơ chế tự động "chạy khi
đủ điều kiện" (idempotent, bỏ qua phần đã hoàn thành, có OS lock + report JSON). Pipeline khoa
học giữ nguyên; không thêm upstream downloader vào runtime FastAPI.

> **Cập nhật (Medallion layering, 2026-11-24):** logic dưới đây nay nằm trong package
> `src/climate_platform/datasets/{noaa,usgs,nldas}/` (mỗi tầng một module); các đường dẫn
> `scripts/process_data/*` chỉ còn entrypoint mỏng. Xem mục "Refactor — Medallion layering" ở trên.

- `scripts/process_data/noaa/run_noaa_bronze_to_gold.py`: auto-runner NOAA. Điều kiện đủ là
  snapshot Bronze mới nhất có `_manifest.json` và đủ 3 CSV daily + `wksst9120.for`; build Silver
  khi thiếu, build Gold khi có Silver và lịch USDM (`--week-dates-csv`/`--usdm-csv`). Hỗ trợ
  `--dry-run`, `--json`, `--report`, `--overwrite`; `--lock-file` mặc định
  `data_lake/temp/noaa_medallion.lock`.
- `scripts/process_data/noaa/noaa_common.py`: thêm `write_json_atomic`, `exclusive_run`,
  `snapshot_complete`, `default_lock_file` dùng chung cho auto-runner.
- `scripts/process_data/noaa/noaa_silver_to_gold.py`: tách thân `main()` thành `build_outputs(...)`
  để runner gọi trực tiếp; CLI giữ nguyên hành vi (in report JSON).
- `scripts/process_data/usgs/run_usgs_bronze_to_gold.py` + `datasets/usgs/runner_cli.py`: auto-runner USGS.
  Điều kiện đủ là `validate()` (không unplanned/unresolved job) và `audit_raw()` PASS; build lần
  lượt Silver → Weekly → Gold, mỗi stage bỏ qua khi đã có run hoàn thành cho upstream hiện tại.
  Lệnh `auto` ở `scripts/process_data/usgs/run_usgs.py auto`; crawler tham khảo ở
  `scripts/process_data/usgs/crawl_usgs.py` (Bronze do Client cung cấp).
- `datasets/noaa/processor.py` (`NoaaProcessor`) và `datasets/usgs/processor.py` (`UsgsProcessor`):
  adapter mỏng cho processing engine, tải module runner từ checkout (`CHECKOUT_ROOT`) khi được gọi;
  `discover()` trả readiness, `run()` trả `ProcessingReport`. `default_registry()` đăng ký
  `usdm`, `noaa`, `usgs`; NLDAS chưa build.

Kiểm chứng local: `ruff check`, `ruff format --check` + import smoke (chưa chạy data thật vì cần
Bronze/USGS API key). NLDAS vẫn theo mẫu `scripts/process_data/nldas/run_bronze_to_gold.py`.

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
