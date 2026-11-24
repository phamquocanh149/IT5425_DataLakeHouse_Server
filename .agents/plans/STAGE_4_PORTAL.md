# Stage 4 — Data Portal

Nguồn chuẩn plan: [AGENT.md](AGENT.md). Rules/convention: [../../AGENTS.md](../../AGENTS.md).

**Trạng thái: Implemented local — Pending UAT (2026-11-22).** Mốc A đã được duyệt, Mốc B đã triển
khai với tài khoản/mật khẩu demo localhost. Chỉ Completed sau B01–B22 đạt trong phạm vi thống nhất
và người dùng nghiệm thu.

| ID | Công việc | Trạng thái / bằng chứng |
|---|---|---|
| S4.01 | Thiết kế UI/permissions/API | DONE Mốc A; docs/STAGE4_DESIGN.md, STAGE4_WIREFRAMES.md, STAGE4_API_CONTRACT.md |
| S4.02 | Password/session, roles/grants | PASS local; production TLS/security deployment còn chờ |
| S4.03 | Catalog/selection/preview/map/download, quality/lineage/history | PASS local API/browser; pin release/file/build; Admin không bypass read grant |
| S4.04 | Immutable release, backup/restore | PASS local copy/hash/SQLite verify và restore root độc lập; process-kill publish drill pending |
| S4.05 | Regression/build/browser | Báo cáo 111 Server + 59 Client tests, 4 browser E2E PASS; Ruff và TypeScript/build PASS |
| S4.06 | UAT và deployment | PARTIAL: total HTTP deadline/disconnect, symlink OS drill, accessibility UAT, clean deploy/sustained load còn chờ |

Implementation `api/portal/`, `../frontend-climate-platform/` React/TypeScript/Vite/MapLibre; opt-in `PORTAL_ENABLED`,
SPA `/portal/`, API `/api/portal/v1`. Browser dùng username/password/session/grants, không dùng key collector.
Không có upload UI, SQL tùy ý hoặc control chạy/retry/cancel pipeline. PortalConfig đọc OS
environment, Compose phải truyền explicit; packaging production chưa nghiệm thu.

Serving root `data_lake/portal`, release `usdm-stage3-v1` là bản sao đã verify, không đọc
`.test-runs` trong request. Baseline: 130 current tuần, 131 historical builds, 625 Silver features,
423.670 Gold rows. Reader subprocess giới hạn memory/time; GIS chạy offline. Timeout mỗi worker
không phải deadline toàn HTTP request. Restore local tại `data_lake/portal-restore-20261122` đã
verify; sessions bị xóa để đăng nhập lại. Không thay thế drill MinIO hoặc backup/restore toàn
pipeline Stage 3.

Benchmark warm local 10 users: p95 catalog 351,1 ms, Gold preview 671,6 ms, Gold map 2.490,8 ms;
không lỗi. Chưa là sustained load/SLA production; còn TLS, reverse proxy/container,
cold-load, proxy disconnect và user UAT.

Nguồn chuẩn: `../../docs/STAGE4_IMPLEMENTATION.md`, checklist `../../docs/STAGE4_ACCEPTANCE.md`,
API `../../docs/STAGE4_API_CONTRACT.md`.
