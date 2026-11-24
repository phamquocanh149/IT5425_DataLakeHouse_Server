# Stage 4 — Portal implementation và demo

Cập nhật 2026-11-22 (Asia/Saigon). Mốc A đã được người dùng duyệt; Mốc B đã có
implementation và kiểm chứng local. **Stage 4 chưa Completed: chờ user UAT và
nghiệm thu cấu hình triển khai thực tế.** Demo dùng tài khoản/mật khẩu cục bộ.

## Mở demo

Truy cập **http://127.0.0.1:8010/portal/** trên máy chạy workspace.
Chọn một tài khoản demo (nút điền sẵn username/mật khẩu) rồi đăng nhập:

| Tài khoản | Mật khẩu | Danh tính · quyền demo |
|---|---|---|
| viewer | viewer-demo | Minh Anh · Viewer — xem/tải Bronze, Silver, Gold |
| operator | operator-demo | Hoàng Nam · Operator — như Viewer, thêm lịch sử attempts đã lưu |
| admin | admin-demo | Quản trị · Admin — quản lý role/grants; có grants dữ liệu seed riêng |
| restricted | restricted-demo | Khách · Chỉ xem Gold — chỉ Gold read, download bị chặn |

Đi từ Tổng quan → Danh mục dữ liệu → tuần → Bronze/Silver/Gold. Dataset Detail có
bảng, bản đồ, schema, quality, lineage và lịch sử. Bronze xem inventory của ZIP;
Silver xem polygon; Gold xem tâm grid, không phải tỷ lệ diện tích hạn hán.
Nút tải lấy toàn bộ artifact của tuần/build đã chọn, không chỉ trang hoặc filter hiện tại.
Admin mở biểu tượng khiên cạnh tài khoản để cấp/thu hồi quyền. Operator không có
nút chạy pipeline. Đăng xuất trước khi đổi tài khoản demo.

Khởi động lại từ root Server:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-portal.txt
npm.cmd --prefix ../frontend-climate-platform ci
npm.cmd --prefix ../frontend-climate-platform run build
.venv/Scripts/python.exe scripts/portal/run_portal_demo.py
```

Demo chỉ bind 127.0.0.1, từ chối host/client ngoài loopback và không tin forwarded
headers. Demo seed tài khoản/mật khẩu công khai trên localhost; **không dùng cho production**.
Không mount module `climate_platform.modules.portal.workers.demo` trong server production.

## Dữ liệu thật và cấu trúc

Serving root: `data_lake/portal`, active release `usdm-stage3-v1`.
Nguồn copy: checkpoint `.test-runs/usdm-stage3` của Stage 3, không đọc checkpoint
đó trong các request Portal. Không sửa dữ liệu `data_crawl_USDM`.

```text
data_lake/portal/
  control.sqlite3             # users, grants, sessions, audit, active pointer
  releases/usdm-stage3-v1/
    release.json             # complete marker và SHA-256 manifest
    catalog.json             # IDs/observations/builds giữ nguyên
    metadata/ingestion.sqlite3
    products/warehouse.sqlite3
    data_lake/bronze/...      # bản sao bytes transport ZIP
    products/...             # Silver GeoParquet, Gold CSV, quality artifacts
    serving/<build_id>/       # bảng scalar, geometry rút gọn theo zoom
  staging/                   # không được API đọc
```

Release giữ 130 observations/current tuần và 131 historical builds. Overview chọn
latest committed build của đúng current observation: **130 tuần, 625 Silver features,
61 geometry repairs, 423.670 Gold rows**. Pilot không cộng vào current. Current hỏng
hoặc chưa build không fallback sang history. Selection user-bound giữ release/file/build
trong 15 phút; đổi active release không đổi selection đang xem. History là lựa chọn rõ ràng.

Tạo release mới, pause ingestion/release writers trước khi chạy; CLI khóa Stage 3 runner:

```powershell
$env:DEBUG='False'
.venv/Scripts/python.exe scripts/portal/prepare_portal.py --source-root .test-runs/usdm-stage3 --portal-root data_lake/portal --gis-python E:/anaconda/python.exe --release-id usdm-next
.venv/Scripts/python.exe scripts/portal/prepare_portal.py --portal-root data_lake/portal --release-id usdm-next --verify
```

Publisher copy và hash artifacts, SQLite backup API, đối soát mọi Gold build CSV
với warehouse, tạo cache từ GeoParquet qua GIS worker riêng, verify rồi publish
atomic. Không ghi đè release ID. GIS không chạy trong API process.

## Module và tích hợp

- `src/climate_platform/app.py`: opt-in `PORTAL_ENABLED`; mặc định tắt, giữ nguyên API collector.
- `src/climate_platform/modules/auth/`, `modules/portal/repositories/store.py`: đăng nhập username/password (PBKDF2),
  cookie HttpOnly, CSRF/Origin, role/grants kiểm tra mỗi request, audit transaction.
- `modules/portal/module.py`, `modules/portal/controllers/*`: catalog/selection/preview/map/download và Admin API trong
  `/api/portal/v1`; SPA cùng origin `/portal/`. Demo dùng cùng module cài routes.
- `releases.py`, `prepare_gis.py`: serving release immutable và offline cache.
- `reader.py`, `read_worker.py`: subprocess riêng cho JSON/SQLite reads; timeout
  5 giây **mỗi worker**, memory cap 256 MiB qua Windows Job Object/Linux RLIMIT_AS.
- `../frontend-climate-platform/`: React/TypeScript/Vite và MapLibre; không gọi tile service bên ngoài.

Preview tối đa 200 rows/trang, 1 MiB response; Gold đọc tối đa 5.000 rows/tuần.
Map tối đa 5.000 features/100.000 vertices/5 MiB. Silver chọn feature intersect
viewport theo bbox và simplify offline; không clip polygon hình học theo viewport.
Rate: metadata 120/phút, preview/map 30/phút/user; 4 preview đồng thời/user.
Download 2 đồng thời/user, 128 MiB/file, không Range, hash kiểm tra trước response;
stream có deadline 60s và audit completed/canceled. Ngân sách worker không bao gồm
auth/hash file; Gold map dùng một worker đọc bảng và một worker tạo GeoJSON.

## Backup/restore đã thử

Pause publish và thay đổi grants trong lúc snapshot. Đích phải mới, không nằm trong
nguồn; không overwrite, không xóa dữ liệu. Copy release không dùng hardlink.

```powershell
.venv/Scripts/python.exe scripts/backup/portal_backup.py --source data_lake/portal --destination data_lake/portal-backup-new
.venv/Scripts/python.exe scripts/backup/portal_backup.py --source data_lake/portal-backup-new --destination data_lake/portal-restored-new
```

Đã chạy copy/restore thật sang `data_lake/portal-restore-20261122`, verify toàn bộ
manifest và SQLite integrity, active release `usdm-stage3-v1`. Restore giữ users/grants/audit
nhưng xóa sessions/transient/leases/usage để bắt buộc đăng nhập lại. Không tái sử dụng
session trước sự cố. Không tự chuyển dịch vụ đang chạy sang thư mục restore.

## Kiểm thử và giới hạn nghiệm thu

Lệnh tái lập:

```powershell
$env:USDM_GIS_PYTHON='E:/anaconda/python.exe'
$env:USDM_SOURCE_ROOT='D:/Trực quan hóa/data_crawl_USDM'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check --no-cache .
.venv/Scripts/python.exe -m ruff format --check --no-cache .
npm.cmd --prefix ../frontend-climate-platform run build
# Khi demo đã chạy trên 8010, Chrome đã cài:
npm.cmd --prefix ../frontend-climate-platform run test:e2e
```

Browser tests dùng Chrome thật, dữ liệu Stage 3 thật và tài khoản demo localhost: overview
counts; preview ba layer; tải ZIP/Parquet/CSV và hash; geometry thật đã render;
Operator/Admin/limited Viewer; mobile không overflow; loading/empty/503/retry/expiry.
Ảnh và trace khi lỗi ở `../frontend-climate-platform/test-results` (không commit).
API tests gồm login đúng/sai/disabled và reset mật khẩu; revoke,
CSRF, cursor, history, release switch, không fallback, corrupt artifact, audit rollback,
rate/concurrency, worker budget, restore. Tests không chứng minh triển khai production.

Kết quả 2026-11-22: **111 Server tests passed** (gồm 30 Portal và GIS thật),
**59 Client tests passed**, **4 browser E2E passed**; Ruff check/format và frontend
TypeScript/build PASS. Một warning Starlette/httpx deprecation từ test dependency.

Đo `scripts/portal/benchmark_portal.py`: 10 users tạm độc lập, mỗi route 10 requests đồng thời,
Windows 10.0.26200, Intel64 Family 6 Model 170. Nearest-rank p95: catalog **351,1ms**,
Gold preview **671,6ms**, Gold map **2.490,8ms**, không lỗi. Đây là sample warm local
ngắn, chưa phải sustained load/capacity hoặc SLA production; script tự xóa users/grants
tạm sau khi chạy và không đổi dữ liệu USDM.

Phần cần nghiệm thu tiếp: TLS/reverse proxy/container packaging, sustained
load/SLO trên hạ tầng đích, hủy download giữa chừng qua proxy, bảo mật deployment, user UAT.
Không chạy real MinIO trong Stage 4; repo không dùng CI/CD. Gate MinIO Stage 2 giữ nguyên.
Bundle bản đồ còn lớn (~343 KiB gzip toàn JS); cần đo cold-load trên mạng triển khai.

## Cấu hình triển khai thực tế

Cài `requirements-portal.txt`, build frontend, mount serving root và frontend/dist
vào existing API deployment. Cấu hình **OS environment** (PortalConfig không tự đọc
`.env`; với Compose cần truyền qua `environment`):

```text
PORTAL_ENABLED=true
PORTAL_DEMO=false
PORTAL_ORIGIN=https://data.example.org
PORTAL_BOOTSTRAP_USERNAME=<username của Admin đầu tiên>
PORTAL_BOOTSTRAP_PASSWORD=<mật khẩu mạnh, qua secret manager>
PORTAL_STORAGE_ROOT=/storage/portal
PORTAL_FRONTEND_ROOT=/app/frontend/dist
```

Bootstrap Admin được tạo ở lần khởi động đầu tiên nếu chưa tồn tại và không tự có
grant đọc dữ liệu. Admin tạo user mới và đặt lại mật khẩu qua `POST /admin/users` và
`PUT /admin/users/{id}/password`. User mới mặc định Viewer không grant. Không dùng API key collector
trong browser. Serving root/control.sqlite3 phải trên local persistent disk, không S3/NFS.
Chưa sửa Compose/Dockerfile để tuyên bố production deploy đã nghiệm thu.
