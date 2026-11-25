# Backlog — chưa gộp vào stage

Nguồn chuẩn plan: [AGENT.md](AGENT.md). Đây là danh sách vấn đề đã ghi nhận nhưng **chưa sửa**;
không mục nào được coi là đã hoàn thành. Giữ ID khi cập nhật.

## Từ Stage 2 (giữ nguyên ID)

| ID | Vấn đề có căn cứ | Tiếp theo / trạng thái |
|---|---|---|
| S2.B1 | Client không đọc Retry-After | TODO riêng; retry 503 có bounded backoff, chưa xử lý quota 429 đúng thời hạn |
| S2.B2 | `/uploads` chưa pagination, Client gọi sau mỗi upload | TODO; thiết kế additive contract rồi benchmark |
| S2.B3 | Temp file write/fsync ở ingestion còn đồng bộ | TODO đo event-loop latency |
| S2.B4 | Default images cần verified digests, source/demo phụ thuộc local image | NEEDS VERIFICATION, chưa clean deploy |
| S2.B5 | TestClient deprecation; docs lịch sử còn encoding/contract lệch | TODO có kế hoạch dependency/docs; không tự đổi HTTPX |
| S2.B6 | Versioning không phải WORM; verify đọc current object | Giới hạn đã biết; KMS/lock/version-history acceptance riêng |
| S2.B7 | `test_upload.py` có thể ghi đè mẫu ở cwd và không fail exit cho mọi lỗi | TODO; không dùng thay nghiệm thu |

## Từ rà soát pristine deploy / Stage 5

Chi tiết bằng chứng xem [STAGE_5_CHECKPOINT.md](STAGE_5_CHECKPOINT.md) mục 5.4.

| ID | Vấn đề có căn cứ | Tiếp theo / trạng thái |
|---|---|---|
| S5.08 | `historical_recipes/` không tồn tại nhưng khai báo trong package-data (extra `portal`/`cryptography` đã bỏ khi chuyển sang password auth) | NEEDS VERIFICATION — clean `pip install`/`build`/`pip check` |
| S5.09 | Compose cần `MINIO_IMAGE`/`MINIO_MC_IMAGE` (image MinIO tự build, pin digest) và artifacts; repo sạch không tự dựng | NEEDS VERIFICATION — template biến nền trường, image pin từ artifacts |
| S5.10 | Import `pyproj.crs`/`transformer` lệch pin `pyproj==3.8.0` | NEEDS VERIFICATION — chạy GIS smoke với pin đúng |
| S5.11 | Chưa chốt đường cài canonical giữa `pyproject.toml` và `requirements*.txt` cho môi trường local | TODO |

## Đa nguồn / analytics (sau Stage 5, chưa triển khai)

| ID | Mục tiêu dự kiến | Dependency / trạng thái |
|---|---|---|
| BL.N1 | Pipeline khoa học NOAA/USGS/NLDAS (mở rộng S3.04) | NOAA/USGS: auto-runner + processor đăng ký (xem S3.04, 2026-11-24); NLDAS processor còn TODO |
| BL.N2 | Silver/Gold trên S3 thay vì chỉ local | PARTIAL 2026-11-25: NLDAS/NOAA/USDM auto-publish qua Dagster đã ghi Silver/Gold lên MinIO; USGS còn lỗi layout, gate image digest/restore vẫn mở |
| BL.N3 | DuckDB/dbt, streaming broker/orchestrator đa nguồn | Không thêm chỉ để khớp tên dự án; cần scope+acceptance; TODO |

Backlog không cấp quyền triển khai; mỗi mục chỉ chuyển sang stage khi người dùng giao rõ scope.
