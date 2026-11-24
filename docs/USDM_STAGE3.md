# Stage 3 — USDM Medallion

Ngày triển khai: 2026-11-21 (Asia/Saigon). Phạm vi được giao mở rộng Stage 3 từ replay
sang toàn bộ Medallion USDM. Các gate vận hành Stage 2 và roadmap đa nguồn Stage 4–5
vẫn độc lập. Không sửa dữ liệu hoặc script trong repo `data_crawl_USDM`.

## Kiến trúc và dữ liệu

Nguồn khảo sát: 130 bộ shapefile USDM M theo tuần, 2020-01-07 đến 2022-06-28.
Tái sử dụng `USDMBronzeToSilverPipeline.process_week` và `GeometryCleaner` của repo
nguồn qua worker riêng. Không chạy crawler hay script R có đường ghi vào repo nguồn.
Giữ API/SQLite registry/Bronze hiện hữu; không thêm broker, database server hoặc
dependency GIS vào requirements của API.

```text
source shapefile sidecars (read-only)
  → deterministic ZIP → existing MetadataManager → Bronze local / S3
  → verified Bronze snapshot → reused cleaner → Silver GeoParquet
  → grid centroid join (maximum DM) → Gold CSV + SQLite analytical tables
```

Gold grain: một `(build_id, grid)` cho một tuần; cột `time,grid,lon,lat,drought`.
Grid lấy duy nhất từ tọa độ CSV tham chiếu, kiểm tra uniqueness và bounds. Drought
được tính lại từ Silver, không sao chép nhãn CSV. `0` = không hạn, `D0` = abnormally dry.
`within` loại điểm đúng trên biên; overlap lấy DM cao nhất. Counts là số ô tâm lưới,
không phải tổng diện tích. Không tái tạo `A.csv` hoặc RDA vì chúng không cần cho mart này.

Lưu trữ dưới output root:

```text
silver/source=usdm/week_date=YYYY-MM-DD/build=<hash>/<content-sha>.parquet
gold/source=usdm/week_date=YYYY-MM-DD/build=<hash>/<content-sha>.csv
quality/source=usdm/week_date=YYYY-MM-DD/build=<hash>/<content-sha>.json
reference/source=usdm/week_date=YYYY-MM-DD/build=<hash>/<content-sha>.csv
warehouse.sqlite3   # builds, attempts, gold_cells; view gold_weekly
last_run.json       # kết quả lần chạy gần nhất
pipeline.lock       # OS lock, file tồn tại không có nghĩa đang bị khóa
```

Manifest trong `builds.manifest` có file_id, revision, raw SHA-256, source member hashes,
recipe hashes, GIS library versions, grid hash và đường dẫn/checksum từng sản phẩm.
`gold_cells` dùng PK `(build_id,grid)`; `gold_weekly` tổng hợp theo build/time/drought.
Bronze dùng layout cũ của Server, không tạo Bronze implementation thứ hai.

## Chạy trực tiếp

Từ root `climate-platform`, dùng Python Server và một Python đã có GIS dependencies.
Môi trường đã kiểm tra: `E:/anaconda/python.exe`, GeoPandas 1.2.0, Shapely 2.2.0,
Pandas 3.0.6, PyArrow 25.0.1. Không cài thêm package trong lần triển khai này.
Cleaner được đọc từ repo nguồn nên phải giữ checkout đó sẵn có; hash thay đổi tạo build mới.

Ví dụ chạy cô lập, không đụng registry production:

```powershell
$env:DEBUG = 'False'
$env:STORAGE_BACKEND = 'local'
$env:BASE_DIR = (Join-Path (Get-Location) '.test-runs/usdm-stage3')
.venv/Scripts/python.exe scripts/process_data/usdm/run_usdm.py `
  --source-root 'D:/Trực quan hóa/data_crawl_USDM' `
  --output-root '.test-runs/usdm-stage3/products' `
  --gis-python 'E:/anaconda/python.exe'
# Có thể giới hạn bằng --start-date 2020-01-07 --end-date 2020-01-07.
# Chạy lại cùng lệnh để kiểm tra replay; CLI exit 1 nếu có tuần lỗi.

.venv/Scripts/python.exe scripts/process_data/usdm/verify_usdm.py `
  --source-root 'D:/Trực quan hóa/data_crawl_USDM' `
  --output-root '.test-runs/usdm-stage3/products' `
  --registry '.test-runs/usdm-stage3/metadata/ingestion.sqlite3'
```

Settings vẫn lấy `.env`/environment như Server. Không ghi credential vào CLI/log.
Runner chỉ được dùng bởi operator tin cậy; không phải endpoint upload mới.
CLI lỗi tổng thể trả exit 1; lỗi từng tuần lưu chi tiết trong attempts/last_run.json,
log stdout chỉ có ngày/trạng thái/loại lỗi. Các tuần khác tiếp tục chạy.

## Truy vấn current, tránh cộng trùng lịch sử

Mở warehouse read-only; attach registry read-only (URI `file:...?...mode=ro` phù hợp
platform, ví dụ dùng `Path.resolve().as_uri() + '?mode=ro'` như script verify).
Sau khi attach dưới tên `registry`, dùng:

```sql
WITH ranked AS (
  SELECT b.*, ROW_NUMBER() OVER (
    PARTITION BY b.file_id ORDER BY b.completed_at DESC,b.build_id DESC
  ) AS rank
  FROM builds b JOIN registry.observations o ON b.file_id=o.file_id
  WHERE o.is_current=1 AND o.status='VERIFIED'
)
SELECT g.time,g.drought,COUNT(*) AS cell_count
FROM gold_cells g JOIN ranked b ON g.build_id=b.build_id
WHERE b.rank=1
GROUP BY g.time,g.drought ORDER BY g.time,g.drought;
```

Revision mới chưa qua quality gate sẽ chưa có Gold current; không dùng revision cũ
thay thế âm thầm. Replay revision cũ không đổi current. Recipe mới tạo build riêng;
view `gold_weekly` cố ý giữ lịch sử, không tự suy luận current.

## Quality, restart và vận hành

- Reject thiếu sidecar bắt buộc, ngày không hợp lệ, tuần trùng, package vượt limit,
  hash Bronze sai, DM fractional/out-of-range, CRS thiếu, geometry không sửa được.
- Silver phải giữ toàn bộ feature; bất kỳ quarantine nào chặn publish cả tuần.
  Gold phải có đúng một dòng cho mỗi grid, không null.
- Publish file tạm + fsync + atomic replace; checksum trước transaction warehouse.
  Commit build và rows trong cùng transaction; fail/kill trước commit để lại orphan
  có thể nhận lại sau xác minh. OS lock được nhả khi process kết thúc.
- Rerun đã hoàn tất kiểm tra checksum, không tạo observation/build/row trùng.
  Product hỏng fail-closed; phục hồi từ backup hoặc reprocess trong output root mới.
- Source/root output phải tách biệt; runner không ghi vào source repo. Bronze giữ bytes
  sidecar trong ZIP xác định, không khẳng định ZIP đó là archive download gốc.
- Backup: dừng runner, dùng SQLite backup API cho cả registry và warehouse, sao lưu
  product tree và Bronze theo runbook backend. Restore vào workspace khác rồi chạy
  verify; không chỉ copy SQLite đang chạy và bỏ WAL. Script backup Stage 2 chưa tự
  bao gồm products/warehouse Stage 3; drill restore Medallion chưa nghiệm thu.

## Kiểm thử và bằng chứng

```powershell
$env:USDM_GIS_PYTHON = 'E:/anaconda/python.exe'
$env:USDM_SOURCE_ROOT = 'D:/Trực quan hóa/data_crawl_USDM'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check --no-cache .
.venv/Scripts/python.exe -m ruff format --check --no-cache .
```

Tests mới gồm replay/revision/lineage, source hashes, corruption Bronze/product,
missing sidecar, limit, retry sau quality failure, orphan adoption, OS lock và SQLite
trigger gây rollback thật. Năm test GIS thật kiểm tra overlap max DM/no drought,
repair topology, fractional DM, out-of-range DM và missing CRS. Không đặt hai nhóm
test này ngang với nghiệm thu real MinIO.

Kết quả ngày 2026-11-21:

| Kiểm tra | Kết quả |
|---|---|
| Full replay dữ liệu thật local | 130 succeeded, 0 failed |
| Replay lần hai | 0 succeeded, 130 skipped, 0 failed; checksum vẫn được kiểm tra |
| Silver | 625 features, 61 geometry repaired |
| Gold current | 423.670 dòng, 3.259 grid × 130 tuần |
| Đối chiếu CSV tham chiếu | 423.670 khớp; 0 mismatch/missing/extra |
| Hash source sidecars và products | Tất cả khớp |
| Full pytest với GIS opt-in | 81 passed, 1 warning deprecation HTTPX có sẵn, 30.82s |
| Sau chỉnh đóng connection catalog | 12 orchestration tests passed, 1.78s; full replay lần hai PASS |
| Ruff check / format | PASS, 37 Python files |

Artifact thực tế: `.test-runs/usdm-stage3/data_lake/bronze`,
`.test-runs/usdm-stage3/metadata/ingestion.sqlite3`,
`.test-runs/usdm-stage3/products/warehouse.sqlite3` và các partition trong products.
Thư mục này được gitignore; không phải dữ liệu production. Một build pilot của tuần
đầu được giữ trong lịch sử do recipe thay đổi lúc triển khai; truy vấn current chọn
đúng 130 build mới nhất, không cộng build pilot. Evidence tổng hợp:
[`USDM_STAGE3_RESULTS.json`](USDM_STAGE3_RESULTS.json).

Giới hạn: output Silver/Gold hiện là local; chưa publish lên bucket Silver/Gold,
chưa đóng gói GIS worker trong Docker, chưa chạy real S3/MinIO/deployment hoặc backup
restore Medallion. Không thay đổi quyền S3 ingestion để lách giới hạn đó.

## Cập nhật Stage 5 (2026-11-22)

Các giới hạn trên là bằng chứng lịch sử Stage 3. Stage 5 bổ sung checkpoint toàn
pipeline/recipe, worker image và GIS test bắt buộc chạy local; xem [runbook](STAGE5_PRODUCTION_READINESS.md).
Build mới tự lưu mã recipe. Recipe pilot lịch sử đã khôi phục bytes khớp đúng hash,
lưu trong vendor/usdm/recipes; không xóa pilot hoặc sửa historical manifest.
