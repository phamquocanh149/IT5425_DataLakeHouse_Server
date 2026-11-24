# Plan chính — Server climate-platform

Cập nhật: 2026-11-23 (Asia/Saigon). Repo này là **Server**; Client là `../climate-collector`.
Đây là **nguồn chuẩn duy nhất cho plan/roadmap**: tiến độ, trạng thái từng stage, task và
acceptance gate. Root `../../AGENTS.md` chỉ chứa rules/convention và index dẫn về đây.

Agent phải đọc file này trước khi chọn việc; roadmap **không** cấp quyền triển khai stage
tiếp theo. Chỉ làm stage/task người dùng đã giao.

| File | Nội dung |
|---|---|
| [AGENT.md](AGENT.md) | Index plan, quy ước trạng thái, tổng quan stage |
| [STAGE_1_BASELINE.md](STAGE_1_BASELINE.md) | Stage 1 ingestion/queue, contract API, module, deployment, bằng chứng baseline |
| [STAGE_2_HARDENING.md](STAGE_2_HARDENING.md) | Stage 2 backup/restore S3, bỏ writer lock, backlog còn lại |
| [STAGE_3_USDM.md](STAGE_3_USDM.md) | Stage 3 USDM Bronze → Silver → Gold/SQLite |
| [STAGE_4_PORTAL.md](STAGE_4_PORTAL.md) | Stage 4 Data Portal |
| [STAGE_5_CHECKPOINT.md](STAGE_5_CHECKPOINT.md) | Stage 5 checkpoint toàn pipeline, phục hồi, pristine deploy |
| [STAGE_6_OPERATIONS.md](STAGE_6_OPERATIONS.md) | Stage 6 vận hành, SLO, mở rộng tải |
| [BACKLOG.md](BACKLOG.md) | Backlog chưa gộp vào stage, gating và thứ tự ưu tiên |

## Quy ước trạng thái

- **DONE** = code/docs và kiểm tra được nêu đã xong, đúng phạm vi ghi kèm.
- **PARTIAL** = còn acceptance gate chưa đóng.
- **TODO** = chưa làm.
- **NEEDS VERIFICATION** = chưa có kết quả trong môi trường cần thiết (Docker, MinIO thật,
  off-host, hai máy).
- Không nâng PARTIAL lên DONE chỉ vì có source code hoặc test mock PASS.
- Bằng chứng lịch sử (PASS cũ) không thay bằng chứng hiện tại.
- Giữ nguyên ID task (`S1.xx`, `S2.Bx`, `S3.xx`, `S4.xx`, `S5.xx`, `S6.xx`) khi cập nhật.
- Mỗi task khi cập nhật phải ghi: trạng thái, file ảnh hưởng, bằng chứng (command/date/test
  count/artifact path), phần còn thiếu và blocker.

## Tổng quan stage

| Stage | Phạm vi thực tế | Trạng thái | Chi tiết |
|---|---|---|---|
| 1 | Baseline ingestion/queue, Bronze/registry, deployment | Local có bằng chứng; clean deploy cần xác minh | [Stage 1](STAGE_1_BASELINE.md) |
| 2 | Backup/restore và SQLite/S3 transactions | PARTIAL: code/tests local xong; real MinIO restore/benchmark và lịch backup còn mở | [Stage 2](STAGE_2_HARDENING.md) |
| 3 | USDM historical replay → Bronze → Silver → Gold/SQLite | DONE trong phạm vi USDM local phía Server; collector tự động Client TODO | [Stage 3](STAGE_3_USDM.md) |
| **4** | **Data Portal xem/tải ba tầng, bản đồ và phân quyền** | **Implemented local — Pending UAT và nghiệm thu deployment** | [Stage 4](STAGE_4_PORTAL.md) |
| **5** | **Checkpoint toàn pipeline và phục hồi, GIS bắt buộc chạy local** | **PARTIAL: code/local tests xong; MinIO/Docker/off-host/pristine deploy còn gate** | [Stage 5](STAGE_5_CHECKPOINT.md) |
| 6 | Vận hành và mở rộng theo tải/SLO | TODO, cần workload và số đo | [Stage 6](STAGE_6_OPERATIONS.md) |

Scope thực tế thay roadmap cũ: Stage 3 đã bao gồm cả Silver/Gold USDM; Stage 4 là Data
Portal; Stage 5 là checkpoint + phục hồi local (thay backlog đa nguồn/analytics, chuyển sang
[backlog](BACKLOG.md)). Các gate MinIO Stage 2 vẫn độc lập và chưa đóng. Các số PASS
Stage 1–4 là bằng chứng lịch sử; kiểm tra Stage 5 ghi riêng trong file Stage 5.

## Gate đang mở (không tự đóng)

- Stage 2: real MinIO restore drill/benchmark, scheduler backup, off-host.
- Stage 4: UAT, TLS, sustained load, process-kill drill.
- Stage 5: pristine deploy từ repo sạch, MinIO/Docker gate, off-host, service RPO/RTO.

## Nguồn chuẩn liên quan

- Rules/convention: [../../AGENTS.md](../../AGENTS.md)
- Module và refactor package: [../../docs/AGENT_MODULES.md](../../docs/AGENT_MODULES.md)
- Vận hành S3: [../../docs/MINIO_OPERATIONS.md](../../docs/MINIO_OPERATIONS.md)
- Tiến độ Client: [../../../climate-collector/AGENT.md](../../../climate-collector/AGENT.md)
