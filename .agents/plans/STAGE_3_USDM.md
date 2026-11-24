# Stage 3 — USDM Medallion Pipeline

Nguồn chuẩn plan: [AGENT.md](AGENT.md). Rules/convention: [../../AGENTS.md](../../AGENTS.md).

**Trạng thái: DONE trong phạm vi batch local USDM đã kiểm chứng ngày 2026-11-21.**
Nguồn `D:/Trực quan hóa/data_crawl_USDM` chỉ đọc: 130 bộ shapefile tuần từ 2020-01-07 đến
2022-06-28. Không chạy crawler hay sửa dữ liệu/script nguồn. Stage 3 mở rộng từ replay sang toàn
bộ Bronze → Silver → Gold; local pilot không đóng hoặc phụ thuộc việc tuyên bố hoàn tất các gate
MinIO Stage 2.

| ID | Công việc | Trạng thái / bằng chứng |
|---|---|---|
| S3.01 | Identity/provenance USDM | DONE local: owner `usdm-replay`, dataset key `usdm/gis/CONUS/M/weekly`, lineage file_id/revision/raw/member/recipe/grid hashes |
| S3.02 | Nhận raw thật | DONE local qua CLI offline và registry hiện có; ZIP xác định giữ bytes sidecars, không phải HTTP upload từ Client |
| S3.03 | Replay/revision | DONE local: 130 succeeded/0 failed; rerun 130 skipped/0 failed; tests corruption/orphan/lock/rollback |
| S3.04 | Mở rộng nguồn khác | PARTIAL: NOAA và USGS có auto-runner Bronze→Gold + `NoaaProcessor`/`UsgsProcessor` đăng ký trong `default_registry()` (2026-11-24, `ruff` + import smoke; chưa chạy data thật vì cần Bronze/USGS API key). NLDAS vẫn theo mẫu `scripts/process_data/nldas/run_bronze_to_gold.py`, chưa đăng ký processor |
| S3.05 | Silver GeoParquet, validation và quality | DONE local: 625 features, 61 repairs; CRS/DM/geometry gate, quarantine chặn publish cả tuần |
| S3.06 | Gold CSV và SQLite warehouse | DONE local: 3.259 grid × 130 tuần = 423.670 rows, 0 mismatch/missing/extra với tham chiếu |
| S3.07 | Lineage/current/history và verify | DONE local: source/product hashes khớp; 130 current builds, 131 historical builds gồm pilot |
| S3.08 | Silver/Gold S3, GIS container, restore Medallion | Stage 5 đã thêm worker image và checkpoint/restore local; build container/MinIO còn gate, Silver/Gold S3 chưa triển khai |

`datasets/usdm/processor.py` điều phối/publish, `datasets/usdm/science.py` chạy GIS trong Python
riêng và tái sử dụng cleaner nguồn; CLI `scripts/usdm/run_usdm.py`, `scripts/usdm/verify_usdm.py`.
Silver/Gold/quality/reference lưu local; `warehouse.sqlite3` có builds/attempts/gold_cells và
gold_weekly. Gold dùng tâm grid, `within`, max DM; `0` khác `D0`, không phải diện tích hạn.
Current chọn observation VERIFIED/current rồi latest committed build đúng file_id; không fallback
sang revision cũ khi current chưa build, không cộng pilot vào current.

Báo cáo ngày 2026-11-21: **81 Server tests passed, gồm 5 GIS tests; Ruff PASS**.
Checkpoint `.test-runs/usdm-stage3` không phải serving root production. Source chỉ đọc, raw bất
biến; dùng checkpoint Stage 5 cho products/warehouse, không dùng backup Stage 2 đơn lẻ.

Chi tiết/lệnh: `../../docs/USDM_STAGE3.md`, kết quả `../../docs/USDM_STAGE3_RESULTS.json`, module
`../../docs/AGENT_MODULES.md`.
