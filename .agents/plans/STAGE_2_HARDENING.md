# Stage 2 — Fix lỗi và củng cố hệ thống (còn gate vận hành)

Nguồn chuẩn plan: [AGENT.md](AGENT.md). Rules/convention: [../../AGENTS.md](../../AGENTS.md).
Trạng thái: **PARTIAL** — code/tests local xong; real MinIO restore/benchmark và lịch backup còn mở.

## 2.1 P0.1 — Backup/restore S3 đầy đủ và thống nhất

**Lỗi gốc:** API-only archive thiếu `minio-data`, có thể restore registry trỏ tới object không
tồn tại.
**Mục tiêu:** một runbook S3 duy nhất, backup cùng checkpoint và restore có thể kiểm chứng.

| ID | Công việc cụ thể | Trạng thái | File / bằng chứng |
|---|---|---|---|
| S2.01.1 | Loại quy trình API-only khỏi luồng S3; ghi rõ legacy local | DONE | `docs/STORAGE_OPERATIONS.md` chỉ legacy, dẫn sang MinIO runbook |
| S2.01.2 | Runbook dừng writers/MinIO, snapshot cả ba volumes, restore vào project mới | DONE docs | `docs/MINIO_OPERATIONS.md`, có lệnh chọn mount/image, không `down -v` |
| S2.01.3 | SQLite `.backup()` cho ingestion + accounting, đóng connections, integrity check | DONE code/tests | `scripts/backup/storage_backup.py`; test committed WAL được backup |
| S2.01.4 | Manifest checkpoint/image/schema/observations, hash/size archive; verify trước restore | DONE code/tests | Thiếu MinIO archive, checksum lỗi bị từ chối; target không rỗng bị từ chối |
| S2.01.5 | Offline restore drill với SQLite và fixture version bytes | DONE local | `tests/backup/test_storage_backup.py`: 5 tests |
| S2.01.6 | Real MinIO restore drill, versions/delete markers, duplicate và RPO/RTO đo được | NEEDS VERIFICATION | Docker engine không kết nối được trong phiên sửa; chưa có chứng cứ real restore |
| S2.01.7 | Lịch backup/drill và lưu off-host | TODO vận hành | Runbook: backup hằng ngày, drill hằng tháng; chưa cài scheduler |

**Acceptance để đóng P0.1 hoàn toàn:** restore sang volumes mới; SQLite integrity OK; mọi
file_id/revision/hash/size/mapping khớp manifest; không missing/corrupt/unmigrated; giải trình
orphan; kiểm chứng historical versions; API ready; gửi lại mẫu thành DUPLICATE không tăng revision;
bản backup ngoài host verify thành công. Ghi report có thời gian thực và người thực hiện.
**RPO mục tiêu <=24h, RTO mục tiêu <=2h**, chưa phải SLA đã chứng minh. Dependency: Docker Linux,
release/image artifacts đúng, quyền backup admin riêng, cấu hình/KMS cần thiết và đủ disk.

## 2.2 P0.2 — Bỏ SQLite writer lock trong S3 I/O

**Lỗi gốc:** BEGIN IMMEDIATE bao trùm PUT/GET; connection nào cũng migrate schema và xin writer lock.
**Mục tiêu:** network không giữ transaction; listing không tranh writer lock; commit ngắn và retryable.

| ID | Công việc cụ thể | Trạng thái | File / bằng chứng |
|---|---|---|---|
| S2.02.1 | Tách initialize() khỏi connection() | DONE | Startup gọi qua threadpool; migration CLI gọi explicit; connection mode=rw không tự tạo DB |
| S2.02.2 | Read snapshot → publish/verify → short transaction re-check | DONE | `catalog/repository.py` S3 registration; giữ unique constraints, key format và response |
| S2.02.3 | Re-check owner/hash/revision/status/mapping sau network | DONE | Test competing owners, identical/different content, status thay đổi giữa GET/commit |
| S2.02.4 | Timeout ngắn và trả 503 + Retry-After thay lock 500 | DONE | `SQLITE_BUSY_TIMEOUT_SECONDS=0.5` (0<value<=5), env/Compose; local và S3 contention tests |
| S2.02.5 | Offload `/uploads` DB I/O khỏi event loop | DONE | `api/app.py` dùng run_in_threadpool; listing vẫn đọc khi DB có writer |
| S2.02.6 | S3 maintenance không giữ writer lock qua network | DONE | `catalog/s3_maintenance.py`: snapshot rồi guarded commit; pause writers vẫn cần cho authoritative report |
| S2.02.7 | Race/failure/orphan/legacy migration regression | DONE local | `tests/api/test_stage2_registry.py`: 12 tests, SQLite thật + S3 fake có barrier/delay |
| S2.02.8 | Benchmark hai upload 20 MiB trên MinIO chậm + real smoke | NEEDS VERIFICATION | Không suy số throughput từ fake S3 tests; Docker engine unavailable |

**Cơ chế hiện tại:** schema migrate một lần mỗi startup (hoặc explicit offline CLI), không mỗi
request. Đọc snapshot trong read transaction ngắn rồi đóng connection. S3 PUT/GET hoàn tất trước
writer transaction. Khi current/duplicate thay đổi, rollback bằng close và chạy lại, tối đa 8 vòng;
không thể đạt trạng thái ổn định thì 503 + Retry-After: 1. Ownership khác trả 403. Duplicate cũ
vẫn giữ is_current=false, không đưa revision cũ thành current. Giữ filename/key/schema/API cũ.

**Tradeoff đã chấp nhận:** race bytes khác có thể publish object của revision dự kiến nhưng không
commit; retry publish theo revision mới, giữ orphan cũ để báo cáo. Không auto-delete raw. Commit
failure cũng có thể để orphan, retry adopt nếu mapping còn đúng. Đây không phải distributed
transaction/exactly-once tuyệt đối. S3 maintenance cần pause writers dù transaction đã ngắn. SQLite
vẫn single writer ở commit; Postgres chỉ xem xét khi có yêu cầu scale ngang và benchmark.

**Acceptance để đóng P0.2 hoàn toàn:** toàn bộ regression/HTTP suites PASS; trong lúc S3 chậm,
listing và upload dataset độc lập vẫn tiến triển; cùng observation chỉ một row; revision chain
đúng, owner không đổi; không VERIFIED khi commit fail; lock contention bounded và trả 503/header;
real MinIO smoke và benchmark dung lượng mục tiêu đạt yêu cầu đã chốt.

## 2.3 Kết quả kiểm thử Stage 2 và phần việc tiếp theo

- Test mới: **12 registry/concurrency tests + 5 backup/restore tests**; chạy lại cả 17 tests sau rà
  soát cuối: PASS (2.30s), gồm lỗi commit SQLite thật. Không cài dependency.
- Full Server suite: **64 passed, 1 warning, 23.47s** (2026-11-20), gồm 7 HTTP loopback integration;
  Ruff check/format PASS cho 31 Python files. Client **59 passed, 1.93s**, Ruff PASS. Warning
  TestClient/HTTPX deprecation vẫn còn.
- Không chạy real MinIO/Compose/restore trên production; Docker engine không kết nối được.
- Khi cập nhật tiến độ: ghi command/date/test count, phần mock vs real, artifact/report path và
  blocker. Chỉ đánh dấu cả Stage 2 DONE sau khi S2.01.6/S2.01.7/S2.02.8 được nghiệm thu hoặc đổi
  scope rõ ràng.

## 2.4 Backlog còn lại, không gộp thành đã sửa

| ID | Vấn đề có căn cứ | Tiếp theo / trạng thái |
|---|---|---|
| S2.B1 | Client không đọc Retry-After | TODO riêng; hiện retry 503 vẫn có bounded backoff, chưa xử lý quota 429 đúng thời hạn |
| S2.B2 | `/uploads` chưa pagination, Client gọi sau mỗi upload | TODO; thiết kế additive contract rồi benchmark |
| S2.B3 | Temp file write/fsync ở ingestion còn đồng bộ | TODO đo event-loop latency; không khẳng định đã sửa cùng listing |
| S2.B4 | Default images cần verified digests, source/demo phụ thuộc local image | NEEDS VERIFICATION, chưa clean deploy |
| S2.B5 | TestClient deprecation; docs lịch sử còn encoding/contract lệch | TODO có kế hoạch dependency/docs; không tự đổi HTTPX |
| S2.B6 | Versioning không phải WORM; verify đọc current object | Giới hạn đã biết; KMS/lock/version-history acceptance riêng |
| S2.B7 | `test_upload.py` có thể ghi đè mẫu ở cwd và không fail exit cho mọi lỗi | TODO; không dùng thay nghiệm thu |

Các mục trên được tổng hợp vào [BACKLOG.md](BACKLOG.md) cùng các backlog mới phát sinh.
