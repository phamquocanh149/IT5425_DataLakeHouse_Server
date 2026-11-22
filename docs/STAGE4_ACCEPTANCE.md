# Stage 4 — Checklist duyệt thiết kế và nghiệm thu

**Status: Implemented local — Pending UAT.** Cập nhật 2026-11-22.
Mốc A đã duyệt; kết quả B dưới đây phân biệt kiểm chứng local với gate deployment.
Chi tiết và lệnh tái lập: [STAGE4_IMPLEMENTATION.md](STAGE4_IMPLEMENTATION.md).
Tham chiếu [Design](STAGE4_DESIGN.md), [Wireframes](STAGE4_WIREFRAMES.md),
[API](STAGE4_API_CONTRACT.md). Dấu checked ở phần A chỉ xác nhận đã bàn giao tài liệu.

## A — Bàn giao thiết kế

- [x] A01: Rà soát AGENT Server/Client, API ingestion, quyền, registry và schema USDM.
- [x] A02: Wireframes Login, Overview, Catalog, Dataset Detail, drawer Admin.
- [x] A03: Permission matrix Viewer/Operator/Admin và scope dataset/layer/action.
- [x] A04: API catalog/selection/preview/map/schema/quality/lineage/download và auth/grants.
- [x] A05: Quy tắc current/history, revision mới chưa có build, artifact hỏng và snapshot.
- [x] A06: Storage serving tách `.test-runs`, checkpoint copy/verify/publish, bảo toàn ID.
- [x] A07: Loading/empty/error/revoked/expired; pagination, map và download bounds.
- [x] A08: Checklist B và tiêu chí không phá Stage 1–3; cập nhật AGENT đúng scope.
- [x] A09 — **Người dùng đã duyệt Mốc A, yêu cầu triển khai B và chọn IdP demo localhost.**

**Gate A đã đạt.** B được triển khai trong scope đã duyệt. Các khác biệt giữa thiết kế
và implementation được ghi ở đầu API contract và runbook; không coi là nghiệm thu production.

## B — Implementation sau khi A09 được duyệt

| ID | Tiêu chí nghiệm thu | Bằng chứng phải có | Trạng thái |
|---|---|---|---|
| B01 | Login/logout, expiry/disabled user; cookie/CSRF; không API key trong browser | Auth unit/integration + OIDC test IdP và deployment cấu hình thật | PASS local OIDC/JWT/cookie/CSRF; production IdP/TLS pending |
| B02 | Không grant → không thấy dataset/count; layer grant độc lập; Admin không bypass read | Ma trận tests ba roles × read/download × layers | PASS API policy + restricted Viewer E2E |
| B03 | Đoán dataset/file/build/artifact/selection ID hoặc sửa cursor không vượt quyền | API negative tests, user A dùng selection user B, path/symlink traversal | PASS API selection/cursor/path checks; symlink OS drill pending |
| B04 | Revoke có hiệu lực request kế tiếp; grant update/audit atomic; conflict không ghi đè | API concurrency/rollback tests; 403 download hoặc 404 read | PASS revoke, If-Match, audit rollback API tests |
| B05 | Catalog đúng quyền, lọc ngày, phân trang ổn định; không thiếu/trùng items giữa trang | API tests với dataset nhiều tuần và nhiều revision/build | PASS immutable release pagination + real 130-week UI |
| B06 | Current chọn registry current rồi latest committed build của đúng file_id | Fixture nhiều revision; artifact hỏng không fallback; old replay không promote | PASS current/no-build/corrupt/no-fallback fixtures |
| B07 | 131 historical builds không thành 131 current tuần hoặc nhân đôi Gold | Với checkpoint Stage 3: 130 tuần/current builds, 423.670 Gold rows | PASS real release: 130 weeks, 423670 Gold rows |
| B08 | History pin đúng version; đổi active release không trộn preview/download | E2E selection + release switch + expired 410 | PASS API history/release-switch/expiry tests |
| B09 | Bronze inventory/hash và ZIP tải khớp registry; không ngụ ý scientific validation | Hash downloaded ZIP + member inventory đối soát source snapshot | PASS publisher hash verification + browser downloaded ZIP hash |
| B10 | Silver rows/schema/CRS và quality đúng Parquet/quality artifact | So sánh một số tuần có/không geometry repair và tổng 625 features khi dùng baseline | PASS GIS-derived cache/publisher verification; browser Silver preview/download |
| B11 | Gold table/download khớp warehouse và CSV của cùng build; 0 khác D0 | Đối soát 423.670 rows baseline + filter/grid/pagination | PASS all-build CSV/warehouse comparison at publication + API/E2E |
| B12 | Map đúng tuần/build, Silver polygon và Gold centers, bounds/drought filters đúng | UI/API sample assertions; geometry display không đổi raw; initial CONUS trong budget | PASS bounded map worker/API + rendered Silver/Gold browser assertions |
| B13 | Schema/quality/lineage không lộ node/metric/path ngoài grant | API tests user chỉ Gold/không Bronze; raw error được redact | PASS restricted lineage/quality and attempts redaction API tests |
| B14 | Operator chỉ xem attempts có thật; không có control hoặc running/progress giả | UI + API capability tests, Viewer bị chặn attempts | PASS Operator/Viewer API + Operator browser flow |
| B15 | Preview/map có hard row/bytes/time/memory limits và rate/concurrency caps | Tests quá limit/deadline, disconnect, worker timeout; không block ingestion event loop | PARTIAL: size/row/memory/worker-time/rate/concurrency PASS; total HTTP deadline and disconnect drill pending |
| B16 | Download kiểm tra quyền/integrity trước 200; stream đúng bytes/headers, không public path | Corrupt/missing artifact, revoked, limit, Range 416; audit completed vs canceled | PASS local hash/revoke/Range/stream; proxy disconnect acceptance pending |
| B17 | Không sử dụng test/source repo làm serving root; copy không sửa/xóa nguồn | Hash trước/sau, path checks, SQLite backup consistency, manifests; không symlink/hardlink | PASS disjoint root, verified copies and SQLite backup; source preserved |
| B18 | Release staging không bị đọc; active pointer atomic, rollback và restore độc lập | Interrupt publish + restore control/release vào root khác rồi verify | PASS independent restore and release-switch tests; process-kill publish drill pending |
| B19 | Loading/empty/error/expired/history; keyboard, labels, responsive, no stale week display | UI component/E2E + walkthrough bốn màn hình bằng browser | PASS 4 browser E2E including mobile/loading/empty/error/expiry; user accessibility UAT pending |
| B20 | Không regression Stage 1–3 và Client contract | Full Server tests có GIS; Client tests + HTTP integration; Ruff và frontend checks | PASS Server 111 + Client 59 + GIS + Ruff + frontend build |
| B21 | Build frontend/Server tái lập; OIDC/domain/storage cấu hình, không credentials trong artifacts | Clean build/deploy + smoke; ghi environment/version/report | PARTIAL: local build/IdP demo PASS; clean production deploy pending |
| B22 | Docs/AGENT/README cập nhật và user nghiệm thu flow xuyên ba tầng | Report command/date/results, artifact paths, limitations, approval | Docs updated; user UAT PENDING |

Mọi count baseline chỉ áp dụng checkpoint Stage 3 đã xác minh; release khác phải có
expected counts theo manifest, không sửa dữ liệu để ép đúng con số cũ. Test GIS cần
được chạy thật hoặc báo blocked, không tính các test skipped là đã đạt.

## Kịch bản UAT chính

1. Viewer có read/download ba layer login, vào USDM, chọn tuần, xem Bronze inventory,
   Silver bảng/bản đồ và Gold bảng/bản đồ; tải ZIP/Parquet/CSV, đối soát hashes.
2. Viewer chỉ Gold không thấy dữ liệu Bronze/Silver qua UI lẫn gọi API trực tiếp.
3. Operator xem attempts của dataset được quyền, không có nút chạy/retry/cancel.
4. Admin cấp Gold read không download; Viewer preview được nhưng tải bị chặn.
   Admin cấp download rồi thu hồi; request kế tiếp phản ánh đúng quyền.
5. Chọn tuần có nhiều build; current chỉ một build, history có thể mở pilot riêng.
6. Revision mới chưa có build: Bronze current có, Silver/Gold “Chưa có sản phẩm”;
   không đưa bản cũ vào current. Build current hỏng: hiển thị unavailable.
7. Giả lập storage lỗi/mạng lỗi/expiry: không báo 0 rows hoặc download sai phiên bản.
8. Chuyển release khi đang xem một selection: dữ liệu vẫn nhất quán tới expiry;
   refresh current mới chuyển snapshot. Rollback release không thay raw.

## Performance và bằng chứng

Với baseline 130 tuần, đề xuất đo 10 người dùng đồng thời trên máy nghiệm thu được
ghi rõ CPU/RAM/storage: p95 catalog/table <2s khi warm; map <5s và đúng payload bound;
không có 5xx ngoài fault injection. Đây là mục tiêu để đo, không phải SLA đã đạt.
Cold-load, GIS memory và download throughput báo riêng. Nếu không đạt thì tối ưu
hoặc trình thay đổi yêu cầu, không đánh dấu PASS từ mock.

Không chạy real S3 trong A; nghiệm thu local B không được mô tả thành nghiệm thu
MinIO production. Nếu chọn Bronze S3 khi deploy, cần test real S3/version-specific
read riêng. Các gate Stage 2 chưa hoàn tất giữ nguyên trạng thái.

**Stage 4 chỉ Completed sau B01–B22 đạt trong phạm vi đã thống nhất và user nghiệm thu.
Mốc A đã có tài liệu không làm thay đổi trạng thái Stage 4 thành Completed.**
