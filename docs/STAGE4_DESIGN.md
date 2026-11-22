# Stage 4 — Data Portal: thiết kế để duyệt

**Status: Design approved; implementation local, pending UAT** · cập nhật 2026-11-22.
Thiết kế v1 bên dưới giữ làm baseline; hiện trạng và các giới hạn triển khai xem
[STAGE4_IMPLEMENTATION.md](STAGE4_IMPLEMENTATION.md).

Mốc A đã được người dùng duyệt và Mốc B đã được triển khai local. Việc có tài liệu,
wireframe hoặc kết quả test Stage 3 không đồng nghĩa Portal đã hoạt động.

## 1. Bộ tài liệu và quyết định cần duyệt

| Tài liệu | Nội dung |
|---|---|
| [Wireframes](STAGE4_WIREFRAMES.md) | Login, Overview, Catalog, Dataset Detail; trạng thái và luồng |
| Tài liệu này | Kiến trúc, quyền, storage, selection, phạm vi |
| [API contract](STAGE4_API_CONTRACT.md) | Session, catalog, preview, map, metadata, download, grants |
| [Acceptance checklist](STAGE4_ACCEPTANCE.md) | Điều kiện duyệt A và nghiệm thu B; chưa ghi PASS cho B |

Đề nghị duyệt các lựa chọn v1:

1. Portal đọc dữ liệu, không upload/điều khiển pipeline/collector hoặc SQL tự do.
2. Login OIDC qua nhà cung cấp danh tính cấu hình ở deployment; session tại FastAPI.
3. Quyền theo dataset và layer; Admin quản lý quyền nhưng không tự có quyền đọc mọi dữ liệu.
4. Bronze xem metadata/danh sách file trong package và tải ZIP; Silver xem bảng/polygon;
   Gold xem bảng/điểm tâm grid. Bản đồ không tự diễn giải số ô thành diện tích hạn hán.
5. Portal dùng một release dữ liệu local, bất biến và riêng biệt; current là current
   tại checkpoint của release. Giao diện luôn hiển thị ngày snapshot.
6. Download nguyên sản phẩm theo tuần/phiên bản; export kết quả lọc hoặc nhiều tuần
   thành file mới nằm ngoài Stage 4.

Issuer/client OIDC, tên miền TLS và đường dẫn persistent storage thực tế là thông số
triển khai phải được cung cấp trước nghiệm thu B; không tự tạo credentials trong A.
Không thêm màn hình đăng ký/reset mật khẩu: do Identity Provider phụ trách.

## 2. Kiến trúc hiện tại và phần thiếu

Đã đọc root/server AGENT, Client AGENT, routes/security/access, metadata/storage,
usdm/usdm_worker, verify_usdm và báo cáo Stage 3. Không chạy lại pipeline hoặc test suite.

| Thành phần | Bằng chứng hiện tại | Hệ quả cho Portal |
|---|---|---|
| Client | HTTPX, queue trên đĩa, API key, CLI; collector upstream còn skeleton | Giữ nguyên Client; Portal không giả lập queue/status từ xa |
| Server | FastAPI `/upload`, `/uploads`, health; không có frontend/session người dùng | API mới dùng namespace riêng; giữ wire contract cũ |
| Registry | SQLite observations, revision, owner, current; Bronze local/S3 | Dùng lại file_id/hash/revision, không tạo identity thay thế |
| USDM | Offline import/replay rồi worker GIS, GeoParquet/CSV/SQLite | Portal chỉ đọc sản phẩm đã publish; không chạy ETL trong request |
| Warehouse | builds, attempts, gold_cells, gold_weekly | `gold_weekly` chứa lịch sử, không cộng tất cả build |
| Attempts | Ngày, status, detail, created_at; không có run_id/heartbeat | Operator thấy lịch sử attempt, không hiển thị “đang chạy” giả |
| Auth hiện tại | API key collector/admin; middleware chỉ bao phủ upload/uploads | Mọi route Portal phải có session/authorization riêng |

Đọc SQLite **read-only** trong lượt rà soát: 130 observations/current USDM,
131 builds trên 130 tuần. Build dư là pilot được giữ lịch sử. Báo cáo Stage 3 ghi
625 Silver features, 61 repairs, 423.670 Gold rows current, 81 test PASS lịch sử;
đây không phải bằng chứng kiểm thử Stage 4.

README workspace/Server còn mô tả Silver/Gold chưa triển khai; khi làm B cần đồng bộ
chúng với AGENT và phạm vi thực tế, không dùng README cũ để suy luận trạng thái dữ liệu.

## 3. Kiến trúc mục tiêu Mốc B

```text
Browser: React + TypeScript
    | HTTPS, cùng origin, session cookie
Reverse proxy
    | /portal → frontend; /api/portal/v1 → FastAPI hiện hữu
FastAPI Portal modules
    | Session + authorization + audit
    | Catalog / selection / schema / quality / lineage
    | Preview / map / bounded download
    +→ Portal control SQLite (users, roles, grants, sessions, audit, active release)
    +→ Release registry snapshot (read-only)
    +→ Release warehouse snapshot (read-only)
    +→ Local Bronze / Silver / Gold artifacts (read-only)

Collector → API ingestion hiện hữu → storage hiện hữu (giữ nguyên)
```

Các module Portal là phần mở rộng của Server, không rewrite ingestion/registry.
Frontend chỉ nhận logical IDs; không nhận đường dẫn máy chủ, credentials S3 hoặc SQL.
API đọc SQLite bằng connection riêng; offload I/O/GIS khỏi event loop. Không mở
khả năng import Python, chạy shell hoặc nhận path tùy ý từ browser.

Preview/map đọc dữ liệu đã chuẩn bị trong release; không dùng `.venv`/Anaconda cá nhân
làm contract production. B cần đóng gói dependencies đọc GeoParquet/map có phiên bản
tái lập. Không cần thêm broker hoặc database server cho Portal đọc một node.

Mở rộng nguồn qua adapter có contract: metadata/schema, preview, map capability,
artifact resolution. Catalog khai báo capabilities từng source/layer; không giả định
NOAA/USGS/NLDAS cũng có tuần, shapefile hoặc cột `drought`. V1 chỉ bật USDM; nguồn chưa
onboard không hiện nút thao tác giả. Ngoài USDM, nhãn partition có thể là ngày/trạm.

## 4. Vai trò và permission matrix

Danh tính Portal là `(OIDC issuer, subject)` ổn định, không dùng email làm khóa owner.
Vai trò ứng dụng lưu phía Server, không nhận role từ payload người dùng.
Một user có một role Viewer/Operator/Admin. Operator và Admin có capability xem
vận hành; quyền dữ liệu vẫn phải được grant rõ ràng.

| Thao tác | Viewer | Operator | Admin |
|---|---|---|---|
| Login/logout, xem session của mình | Có | Có | Có |
| Catalog/Overview dataset | Theo grant `read` | Theo grant `read` | Theo grant `read` |
| Preview/schema/quality/map | Theo layer được `read` | Như Viewer | Như Viewer |
| History của dataset/layer | Theo `read`; gồm lịch sử | Như Viewer | Như Viewer |
| Download | Cần `read` + `download` trên layer | Như Viewer | Như Viewer |
| Lineage | Chỉ node được `read`; node khác bị che | Như Viewer | Như Viewer |
| Lịch sử attempt xử lý | Không | Dataset có ít nhất một layer được `read` | Như Operator |
| Xem danh mục tên dataset để cấp quyền | Không | Không | Có; không kèm dữ liệu/quality/count |
| Quản lý role/grants của người dùng | Không | Không | Có, audit bắt buộc |
| Xem audit quản trị | Không | Không | Có; không chứa raw payload/secrets |
| Upload/chạy lại pipeline/điều khiển collector/SQL | Không | Không | Không trong Stage 4 |
| Xóa raw/sửa dữ liệu/đổi current build | Không | Không | Không trong Stage 4 |

Grant v1: `(user_id, dataset_id, layer, actions={read,download})`; dataset_id ánh xạ
duy nhất `(source,dataset_key)`. `download` yêu cầu `read`. Không wildcard hoặc deny
chồng chéo trong v1; không có grant nghĩa là từ chối. Grant bao phủ các tuần và
history của dataset/layer đó. Nếu cần hạn chế từng tuần, phải sửa thiết kế trước B.

Admin có thể cấp quyền cho chính mình nhưng hành động phải được audit. Không tự
đổi owner `usdm-replay` hoặc owner collector trong registry. Không cho UI đổi role
của chính Admin hoặc vô hiệu hóa Admin cuối cùng. Bootstrap Admin là thao tác cấu hình
deployment có kiểm soát, không dựa vào “người login đầu tiên”. User mới mặc định
Viewer nhưng chưa có grant; hiển thị “Chưa được cấp dữ liệu”.

UI quản lý quyền là drawer từ menu Admin, không phát sinh dashboard vận hành mới.
Chỉ quản lý user đã đăng nhập ít nhất một lần; tạo account/MFA thuộc Identity Provider.

Áp dụng quyền trên mỗi request, trước count/pagination/cache/download. Session chưa
xác thực trả 401; object không tồn tại hoặc ngoài phạm vi nhìn thấy trả 404 cùng dạng.
Object thấy được nhưng thiếu quyền download trả 403. Backend không tin nút ẩn phía UI.
Điều này bám theo nguyên tắc deny-by-default và kiểm tra quyền mỗi request của
[OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).

## 5. Login/session

OIDC Authorization Code + PKCE; backend kiểm tra issuer/audience/signature/nonce/state
và exact redirect URI. Nút Login chuyển sang IdP; token không lưu trong localStorage.
Session opaque tại Server, cookie `HttpOnly`, `Secure`, `SameSite=Lax`, Path `/`;
rotate session khi đăng nhập. Idle 30 phút, absolute 8 giờ là mặc định đề xuất.
POST/PUT/PATCH/DELETE yêu cầu CSRF token và kiểm tra Origin, gồm logout và grants.
Các giới hạn này là quyết định thiết kế, không phải config đã tồn tại.

Role/grants được kiểm tra từ control store mỗi request; revoke có hiệu lực với request
kế tiếp, không chờ token hết hạn. Stream đang mở không thể thu hồi bytes đã gửi;
download mới phải kiểm tra lại. Disabled user/session hết hạn trả 401. IdP lỗi không
fallback sang API key. API key collector/admin hiện hữu không đăng nhập Portal.
Đề xuất cookie/session theo [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

## 6. Vùng dữ liệu Portal riêng — chỉ thiết kế, chưa tạo

Ví dụ local: `<workspace>/data_lake/portal`; production: persistent local volume
`/storage/portal`. Cấu hình dự kiến `PORTAL_STORAGE_ROOT`; cấm resolve vào `.test-runs`,
`.smoke`, repo dữ liệu nguồn hoặc symlink dẫn tới các vùng đó.

```text
portal/
  control.sqlite3                 # session/grant/audit + active_release_id
  releases/<release_id>/
    metadata/ingestion.sqlite3    # snapshot nhất quán, giữ nguyên file_id/revision
    data_lake/bronze/...          # bản sao bytes thật; cùng layout relative của registry
    products/warehouse.sqlite3   # snapshot builds/attempts/gold_cells
    products/silver|gold|quality|reference/...  # giữ layout manifest Stage 3
    serving/                     # index preview/map rút gọn, suy ra từ artifact
    release.json                 # nguồn checkpoint, hashes, schema, as_of, trạng thái
```

Không dùng mount/symlink/hardlink về dữ liệu test. Browser/API không truy cập trực tiếp
`.test-runs`, dù thông qua URI hay registry mapping. Snapshot lineage vẫn giữ ID gốc;
release_id chỉ định checkpoint phục vụ, không thay dataset/file/build identity.

Kế hoạch chuẩn bị ở B:

1. Chọn checkpoint Stage 3; khóa/dừng writer liên quan trước khi snapshot registry
   và warehouse bằng SQLite backup API. Không copy DB đang hoạt động rồi bỏ WAL.
2. Sao chép nguyên byte Bronze/products vào release staging mới, không move/xóa nguồn.
   Dữ liệu test có thể là nguồn copy lần đầu nhưng phải kiểm tra độc lập trước publish.
3. Kiểm tra SHA-256/size và mọi mapping local; từ chối mapping thoát root. Giữ các
   revision/build thuộc checkpoint, gồm pilot lịch sử. Tạo index row/map có hash input.
4. Đối soát Gold CSV với warehouse theo build; kiểm tra current và source/reference hashes.
5. Đóng snapshot, đánh dấu release complete rồi cập nhật active_release_id trong một
   transaction control store. API không thấy staging; rollback chỉ đổi pointer release.

Release v1 dùng Bronze local để nghiệm thu xuyên ba tầng bằng bộ dữ liệu đã có.
Backend vẫn giữ khả năng Bronze S3 hiện hữu; nếu deployment chọn S3 cho Portal, phải
bổ sung acceptance real S3/version-specific download trước khi công bố hỗ trợ đó.
Silver/Gold vẫn local; không mở quyền bucket mới. Không thay cấu hình ingestion đang chạy.

Snapshot được refresh qua vận hành có kiểm soát ngoài UI. Không hiển thị snapshot là
trạng thái live. Operator thấy attempt đã ghi tới `as_of`, không thấy progress hiện thời.
Backup Portal phải bao gồm control store + release đang phục vụ; chưa có restore drill
cho phần này ở Mốc A. Nghiệm thu B cần khôi phục được release trên vị trí độc lập.

## 7. Quy tắc current/history

Đơn vị: dataset `(source,dataset_key)` → tuần `source_date` → observation `file_id`
và `revision` → build → artifact của layer. USDM key là `usdm/gis/CONUS/M/weekly`.

**Current tại release:**

1. Tìm observation `is_current=1` của dataset/tuần, rồi kiểm tra `status=VERIFIED`.
   Nếu current không VERIFIED: trạng thái unavailable; không lấy revision cũ thay thế.
2. Bronze lấy đúng raw/file_id của observation đó.
3. Silver/Gold lấy các build đã commit thuộc chính file_id đó. Chọn lớn nhất theo
   `(completed_at,build_id)`; cùng một build cho Silver/Gold/quality/reference.
4. Kiểm tra artifact/integrity của build đã chọn. Hỏng hoặc thiếu thì unavailable,
   không fallback sang build cũ. Không có build thì `not_built`, không phải 0 rows.
5. Attempt lỗi mới hơn không xóa build đã commit: vẫn phục vụ build current và nêu
   riêng latest attempt cho Operator. Không suy ra attempt là build hoặc run đang chạy.

**History:** người dùng chọn explicit file_id; có thể chọn build_id thuộc file_id đó.
Nếu chỉ chọn file_id, chọn build đã commit mới nhất của file đó như trên. Old revision
không được đổi current. Chọn build khác file_id/dataset/tuần trả 422; không tự sửa selector.

Selection response pin release_id/file_id/build_id và phát token thời hạn 15 phút.
Preview/map/schema/quality/lineage/download dùng cùng token. Đổi tuần/phiên bản tạo
selection mới và xóa dữ liệu UI cũ. Khi active release đổi, selection đang xem tiếp tục
trỏ release cũ cho tới expiry, UI ghi snapshot cũ; không trộn trang từ hai release.
Giữ release tối thiểu bằng TTL và thời gian request đang dùng; hết hiệu lực trả 410.
Token không thay authorization; revoke grant vẫn bị chặn ngay request kế tiếp.

Overview đếm DISTINCT dataset/tuần/observation theo quyền, chỉ cộng rows của build
được chọn mỗi tuần. Không cộng trực tiếp `gold_cells`/`gold_weekly` toàn lịch sử.
Với checkpoint đã rà soát: catalog có 1 dataset, 130 tuần, 130 current observations,
130 selected builds và 423.670 Gold rows; history có 131 builds. Đây là baseline dữ liệu,
không hardcode vào UI hoặc ép các release tương lai phải có đúng số đó.

## 8. Kết thúc Mốc A

Chỉ tạo/sửa tài liệu thiết kế và AGENT. Không tạo frontend, API, migration, auth,
data release hoặc test code. Bộ kiểm tra runtime Stage 1–3 không chạy lại cho thay đổi
tài liệu; số PASS cũ chỉ dùng làm baseline. Duyệt design mới mở gate Mốc B.
