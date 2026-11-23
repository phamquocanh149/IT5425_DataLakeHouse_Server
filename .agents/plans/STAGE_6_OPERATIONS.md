# Stage 6 — Vận hành và mở rộng theo tải

Nguồn chuẩn plan: [AGENT.md](AGENT.md). Rules/convention: [../../AGENTS.md](../../AGENTS.md).

**Trạng thái: TODO, có điều kiện.** Không tự thay SQLite bằng Postgres chỉ vì có roadmap.
Không triển khai mục nào dưới đây khi chưa có workload/SLO hoặc quyết định của người dùng.

| ID | Công việc | Dependency | Acceptance |
|---|---|---|---|
| S6.01 | Định nghĩa/đo throughput, p95 latency, backlog và recovery | Workload/SLO được chốt | Có số baseline tái lập và ngưỡng cảnh báo |
| S6.02 | Metrics/log retention/central audit | Chính sách dữ liệu và hạ tầng logs | Mất dependency/queue stall phát hiện được, log không lộ secrets |
| S6.03 | Pagination và tối ưu commit path | S6.01, contract tương thích | Client cũ vẫn chạy; tải mục tiêu đạt SLO |
| S6.04 | Postgres/shared limiter/outbox nếu scale ngang cần thiết | Benchmark chứng minh SQLite không đáp ứng, migration plan | Fault/concurrency/migration tests bảo toàn identity/revision/raw và rollback khả thi |

Dependency mở: S6.03 phụ thuộc S2.B2 (pagination contract); S6.04 chỉ sau khi S6.01 có số đo chứng
minh SQLite không đáp ứng.
