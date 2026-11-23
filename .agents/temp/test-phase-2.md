# Test Phase 2 — Object Storage First

## Hiện trạng

Phase 2 S3-first **chưa có trong code**: `src/climate_platform/datasets/usdm/processor.py:281-299`
vẫn ghi Silver/Gold/quality/reference xuống `--output-root` local. MinIO hiện chỉ được cấp
quyền ghi Bronze (`scripts/ops/minio-init.sh:19-20`). Vì vậy, sau khi chạy USDM, bucket
`climate-silver` và `climate-gold` còn trống là **đúng hiện trạng**, không phải lỗi test.

Mục tiêu của Phase 2: đưa Silver/Gold, build artifacts, manifests và reference datasets
lên S3/MinIO; local chỉ còn workspace tạm; giữ nguyên revision, lineage và Gold hiện hành.

## 0. Chuẩn bị

- Docker Desktop đang chạy với Linux containers.
- Repo Server: `D:\Trực quan hóa\DataLake_Warehouse\climate-platform`.
- Nguồn USDM: `D:\Trực quan hóa\data_crawl_USDM`.
- GIS Python: `E:\anaconda\python.exe`.
- Không chạy `docker compose down -v`.

## 1. Khởi động stack

```powershell
cd 'D:\Trực quan hóa\DataLake_Warehouse\climate-platform'

docker compose up -d --build --wait --wait-timeout 120
docker compose ps -a
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

Kỳ vọng: `api` và `minio` healthy; `minio-init` Exited (0). API: <http://127.0.0.1:8000>.
MinIO Console: <http://127.0.0.1:9001>.

## 2. API key — nguyên nhân lỗi 401

Repo đang chạy `ENABLE_STATIC_KEYS=False` (xem `.env`), nên static key
`COLLECTOR_API_KEY=test_01` **không còn hiệu lực**. API chỉ chấp nhận rotating key
`key_id.secret` có `secret_hash` khớp record trong `API_KEYS`.

Credential collector hiện có nằm ở:

```text
D:\Trực quan hóa\DataLake_Warehouse\.runtime\collector-credential.txt
```

Nạp vào PowerShell, không in ra log:

```powershell
$collectorKey = (Get-Content -LiteralPath '..\.runtime\collector-credential.txt' -Raw).Trim()
```

Không dùng `COLLECTOR_API_KEY` trong `.env` để test upload; đó là static key đã tắt.
Nếu credential hết hạn hoặc không khớp, tạo bộ key mới bằng `scripts/ops/create_api_key.py`
và cập nhật `API_KEYS` trong `.env` rồi recreate API.

## 3. Test upload API → MinIO Bronze

Dùng file có tên riêng để tránh trùng `dataset_key` với observation cũ của identity khác:

```powershell
$sample = Join-Path $env:TEMP ('phase2-usdm-' + (Get-Date -Format 'yyyyMMddHHmmss') + '.csv')
@"
date,fips,county_name,state,none,d0,d1,d2,d3,d4
2026-11-23,01001,Autauga County,AL,100.0,0.0,0.0,0.0,0.0,0.0
"@ | Set-Content -LiteralPath $sample -Encoding utf8

.\.venv\Scripts\python.exe scripts/ops/test_upload.py `
  --api-key $collectorKey `
  --file $sample `
  --source usdm `
  --source-date 2026-11-23

.\.venv\Scripts\python.exe scripts/ops/test_upload.py --api-key $collectorKey --list
```

Kỳ vọng: HTTP 200, `status=VERIFIED`, `stored_path` bắt đầu bằng `s3://climate-bronze/`,
`SHA-256 Verification: MATCH!`. Chạy lại cùng file có thể trả `DUPLICATE` nhưng vẫn HTTP 200.

Nếu gặp `403 Dataset belongs to another identity`, đổi tên file/source_date để có
`dataset_key` mới; không dùng filename mẫu `sample_usdm_drought.csv` đã thuộc identity khác.

## 4. Kiểm tra object và version trong MinIO

`mc` chạy trong container `minio-init`; mỗi lệnh dưới đây là một lần chạy riêng (không dùng
vòng lặp `for` trong một dòng vì PowerShell/Compose trên Windows làm hỏng quoting).

```powershell
# Danh sách bucket
docker compose run --rm --no-deps --entrypoint /bin/sh minio-init -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; mc ls lake'

# Object Bronze
docker compose run --rm --no-deps --entrypoint /bin/sh minio-init -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; mc ls --recursive lake/climate-bronze'

# Version/revision Bronze
docker compose run --rm --no-deps --entrypoint /bin/sh minio-init -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; mc ls --versions --recursive lake/climate-bronze'

# Silver/Gold/Warehouse (hiện trống vì Phase 2 chưa code)
docker compose run --rm --no-deps --entrypoint /bin/sh minio-init -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; mc ls --recursive lake/climate-silver'
docker compose run --rm --no-deps --entrypoint /bin/sh minio-init -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; mc ls --recursive lake/climate-gold'
docker compose run --rm --no-deps --entrypoint /bin/sh minio-init -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null; mc ls --recursive lake/climate-warehouse'
```

Trong MinIO Console (<http://127.0.0.1:9001>), đăng nhập bằng `MINIO_ROOT_USER` /
`MINIO_ROOT_PASSWORD` trong `.env`; chọn bucket `climate-bronze` và bật **Versions** để xem
lịch sử object. Đây là web UI của MinIO; `mc` chỉ là CLI, không có giao diện web riêng.

## 5. Chạy USDM 1 tuần (Bronze → S3, Silver/Gold → local)

```powershell
$env:DEBUG='False'
$env:STORAGE_BACKEND='s3'
$env:S3_ENDPOINT='http://127.0.0.1:9000'
$env:BASE_DIR=(Join-Path (Get-Location) '.test-runs\phase2-smoke')

.\.venv\Scripts\python.exe scripts/usdm/run_usdm.py `
  --source-root 'D:\Trực quan hóa\data_crawl_USDM' `
  --output-root '.test-runs\phase2-smoke\products' `
  --gis-python 'E:\anaconda\python.exe' `
  --start-date 2020-01-07 --end-date 2020-01-07
```

Kỳ vọng: `{"succeeded": 1, "skipped": 0, "failed": 0}`; Bronze raw được upload lên
`climate-bronze`; Silver/Gold/quality/reference nằm dưới
`.test-runs\phase2-smoke\products`.

## 6. Verify hash, lineage và Gold

```powershell
.\.venv\Scripts\python.exe scripts/usdm/verify_usdm.py `
  --source-root 'D:\Trực quan hóa\data_crawl_USDM' `
  --output-root '.test-runs\phase2-smoke\products' `
  --registry '.test-runs\phase2-smoke\metadata\ingestion.sqlite3'
```

Kỳ vọng: `weeks=1`, `matched_cells=3259`, `mismatched_cells=0`,
`missing_cells=0`, `extra_cells=0`, `source_and_product_hashes_verified=true`.

## 7. Test replay/idempotency

Chạy lại đúng lệnh ở mục 5. Kỳ vọng: `{"succeeded": 0, "skipped": 1, "failed": 0}`,
không tạo build/revision mới; manifest cũ vẫn được kiểm tra checksum.

## 8. Kiểm tra S3-first sau khi Phase 2 được implement

Sau khi code Phase 2 xong, chạy lại mục 3–6 và thêm các assert:

- `climate-silver` có object `source=usdm/...` (Silver GeoParquet).
- `climate-gold` có object `source=usdm/...` (Gold CSV).
- `climate-warehouse` có manifest/warehouse artifact theo thiết kế Phase 2.
- `.test-runs\phase2-smoke\products` không còn là nơi lưu bền vững Silver/Gold;
  chỉ còn workspace tạm.
- Chạy lại replay vẫn `skipped=1`; manifest/manifest lineage trỏ tới object key S3 và
  `verify_usdm` vẫn khớp hash.
- Versioning của bucket giữ được revision cũ; `mc ls --versions --recursive lake/climate-gold`
  thể hiện lịch sử khi có revision mới.

## 9. Regression và smoke

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke/cross_repo_smoke.py
.\.venv\Scripts\python.exe scripts/smoke/compose_smoke.py
```

`compose_smoke.py` tạo project/bucket/credential riêng và kiểm tra Client thật →
API → MinIO; không dùng credential dev ở trên và không thay thế test USDM.
