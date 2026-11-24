# Stage 4 — Portal API contract v1 (proposed)

**Design approved; routes đã triển khai local trong `src/climate_platform/api/portal/`.**
Baseline thiết kế dưới đây được đối chiếu với [implementation](STAGE4_IMPLEMENTATION.md).
Khác biệt v1 cần biết: login redirect 307; request ID luôn có ở header, một số
success payload không lặp ID; Admin audit hiện chỉ cửa sổ 1.000 events mới nhất,
chưa hỗ trợ after/before; Admin list dùng offset cursor, chưa snapshot mutable users.
Metadata dataset pages pin immutable release. Tối đa 20 selection/user, tạo selection
mới evict selection cũ nhất. Map Silver bbox-filter, không geometry clipping.
Timeout 5s áp dụng mỗi reader subprocess, không phải hard deadline toàn HTTP request.
Contract hiện hữu `/upload`, `/uploads`, `/livez`, `/readyz`, `/health` và API key
collector giữ nguyên. Tài liệu này không thay [API_CONTRACT.md](API_CONTRACT.md).
Tham chiếu [kiến trúc/quyền/selection](STAGE4_DESIGN.md).

## 1. Quy ước

- Prefix `/api/portal/v1`; JSON UTF-8; date `YYYY-MM-DD`, timestamp RFC3339 UTC.
- Cùng origin với frontend. Session cookie, backend authorization trên mọi route
  trừ `/auth/login` và `/auth/info`. CSRF + Origin cho mọi phương thức thay đổi trạng thái.
- Không query param path, bucket, SQL, Python executable, source-root hay raw URL.
- dataset_id là opaque ID ánh xạ source/dataset_key trong catalog release; giữ ổn định
  giữa releases: đề xuất `ds_` + SHA-256 của source, ký tự NUL phân cách và dataset_key
  UTF-8 (identity hiện hữu cấm control characters nên không mơ hồ). Không đổi dataset_key.
  file_id/build_id là ID gốc. version_id/artifact_id/selection_id là
  opaque ID được Server cấp và resolve trong phạm vi user/dataset/release.
- Không trả stored_path, S3 credentials, local usernames, stderr hoặc traceback.
- Success JSON có `request_id`; lỗi có `error.code`, `error.message`, `request_id`,
  `retryable`. Headers dữ liệu/session: `Cache-Control: private, no-store`.
- Mỗi list lọc quyền trước phân trang/count. Không dùng pagination để đọc vượt grant.

## 2. Auth và quản trị quyền

| Method / route | Input | Response / điều kiện |
|---|---|---|
| GET `/auth/info` | Không | 200 `demo` và danh sách tài khoản demo khi `demo=true`; rỗng ngoài demo |
| POST `/auth/login` | `username`, `password` | 200 user/role/csrf_token, set cookie HttpOnly; 401 sai credentials/disabled |
| GET `/session` | Cookie | 200 user_id/username/display_name/role/csrf_token; 401 nếu invalid |
| POST `/auth/logout` | CSRF header | 204, hủy session Server/cookie |
| POST `/admin/users` | `username`, `display_name`, `role`, `password` | Admin; 201 user mới; 409 nếu trùng username |
| PUT `/admin/users/{id}/password` | `password`; `If-Match: <version>` | Admin; 204, reset mật khẩu; 404/412/428 |
| GET `/admin/users` | `q`, `limit`, `cursor` | Admin; user_id/username/display_name/role/enabled/version |
| PATCH `/admin/users/{id}` | `role`, `enabled`; `If-Match: <version>` | Admin; 200 user mới/version; cấm tự đổi role/enabled, bảo vệ Admin cuối |
| GET `/admin/datasets` | `q`, `limit`, `cursor` | Admin; ID/source/display_name/layers, không rows/quality/artifacts |
| GET `/admin/users/{id}/grants` | Pagination | Admin; danh sách grant + version |
| PUT `/admin/users/{id}/grants/{dataset_id}/{layer}` | `actions`, `If-Match` | Admin; actions subset read/download, download cần read |
| DELETE `/admin/users/{id}/grants/{dataset_id}/{layer}` | `If-Match` | Admin; 204; request kế tiếp bị kiểm tra quyền mới |
| GET `/admin/audit` | `after`, `before`, `limit`, `cursor` | Admin; actor/action/target/result/time/request_id, đã lọc secrets |

PUT tạo grant dùng `If-None-Match: *`; cập nhật/xóa dùng If-Match. Conflict trả 412;
thiếu precondition trả 428. API kiểm tra các field allowlist, không mass assignment.
Audit mutation và grant update cùng transaction control store; audit lỗi thì không
commit quyền. Admin đầu tiên bootstrap bằng cấu hình trước deployment. Không route
public đăng ký user hoặc route tự cấp role. User bị disabled/session thu hồi trả 401.

## 3. Discovery và overview

| Method / route | Input | Kết quả |
|---|---|---|
| GET `/overview` | `source?`, `release_id?` | Count theo quyền, phạm vi ngày, tình trạng layer, release_id/as_of |
| GET `/sources` | `release_id?` | Nguồn có dataset được read; capabilities, partition_kind |
| GET `/datasets` | `source?`, `q?`, `layer?`, `from?`, `to?`, `limit`, `cursor`, `release_id?` | Dataset summaries, các layer được read, phạm vi ngày |
| GET `/datasets/{id}` | `release_id?` | Mô tả, source, dataset_key, capabilities, schema overview theo quyền |
| GET `/datasets/{id}/weeks` | `from?`, `to?`, `limit`, `cursor`, `release_id?` | Một item/tuần, current revision và availability các layer được read |
| GET `/datasets/{id}/weeks/{week}/versions` | `limit`, `cursor`, `release_id?` | History, version_id, revision, build_id nếu được xem, is_current, completed_at |
| GET `/datasets/{id}/attempts` | `from?`, `to?`, `limit`, `cursor`, `release_id?` | Operator/Admin có read; attempt_id/date/status/created_at/safe_reason |

`q` tối đa 100 ký tự, không regex; dates ISO hợp lệ, from <= to. Source chỉ giá trị
đã onboard, layer thuộc bronze/silver/gold. V1 `/weeks` là partition endpoint của
adapter USDM; nguồn mới dùng contract partition phù hợp, không ép mọi nguồn thành tuần.

List response: `items`, `page={limit,next_cursor}`, `release_id`, `as_of`, `request_id`.
History với user chỉ có Bronze read trả một item/observation, không lộ số build hoặc
thời gian build derived. User có Silver/Gold read mới thấy các version build tương ứng.
Admin/dataset listings và overview không được dùng history count để lộ layer ngoài grant.

Default limit 25, max 100; cursor opaque ký xác thực ràng buộc user, release, filters,
sort và last key. Cursor TTL 15 phút; đổi filter/limit phải quay trang đầu.
Không cho offset tùy ý hoặc order_by SQL từ browser. Không cần exact total ở mọi list.

Sort cố định: datasets `(display_name,dataset_id)` tăng; weeks date giảm; versions
revision giảm, completed_at giảm, build_id giảm (observation chưa có build cũng có
version item); attempts `(created_at,attempt_id)` giảm; admin lists theo ID tăng,
audit `(timestamp,event_id)` giảm. User/admin lists pin watermark ở cursor; dữ liệu
quyền luôn recheck mới nhất, UI refresh sau mutation. Counts không bao gồm object bị ẩn.

Request đầu không có release_id chọn active release; response pin ID. Frontend truyền
ID đó cho các request liên quan. Cursor tự pin release nên cấm request mâu thuẫn ID.
Snapshot không còn phục vụ trả 410; DB/storage lỗi trả 503, không trả list rỗng thay lỗi.

## 4. Selection — một lựa chọn xuyên preview/map/download

`POST /selections` (session + CSRF) nhận:

| Field | Quy tắc |
|---|---|
| dataset_id | Bắt buộc, phải có ít nhất một layer read |
| week | Bắt buộc, ISO date có trong dataset/release |
| release_id | Bắt buộc, lấy từ catalog/overview |
| mode | `current` hoặc `history`; default current |
| version_id | Bắt buộc khi history, cấm khi current; lấy từ versions |

History version_id ánh xạ đúng file_id/build_id của tuần/dataset/release đó, không tự
đổi thành bản mới nhất. Versions có thể phát một item observation chưa có build:
chọn item đó vẫn xem Bronze được. Internal selection thực thi rules tại mục 7
[STAGE4_DESIGN.md](STAGE4_DESIGN.md), không nhận đường dẫn artifact từ browser.

Response 201: selection_id, expires_at, release_id, as_of, dataset_id, week, mode,
revision, `build_id` (null nếu chưa có/không được xem derived layer), `file_id` (chỉ
trả nếu có Bronze read), layers và request_id. layers chỉ chứa layer được read:

| Layer field | Ý nghĩa |
|---|---|
| availability | `available`, `not_built`, `unavailable` |
| reason_code | null hoặc mã an toàn như INPUT_UNVERIFIED / ARTIFACT_UNAVAILABLE |
| verification | Bronze `bytes_verified`; derived `quality_passed` hoặc unknown |
| capabilities | table/map/schema/quality/lineage/download theo layer và quyền |
| artifacts | artifact_id, format, size_bytes, sha256, download_allowed |

Selection là opaque state Server, user-bound, TTL 15 phút, tối đa 20 selections đang
sống/user; cấm dùng selection của người khác. Mỗi endpoint con vẫn recheck grant.
Thu hồi một layer không thu hồi các layer khác: request layer bị thu hồi trả 404.
UI phải refresh session/capabilities; không cache dữ liệu private qua logout.

## 5. Preview và metadata

Prefix các route sau: `/selections/{selection_id}/layers/{layer}`.

| GET route | Params | Response |
|---|---|---|
| `/preview` | limit default 50/max 200, cursor; Gold có `drought?`, `grid?` exact match | columns, rows, page, matched_count, selection metadata |
| `/schema` | Không | fields: name/type/nullable/description/unit; CRS/geometry nếu có |
| `/quality` | Không | metrics/rules có trong artifact của layer, provenance, checked_at khi biết |
| `/lineage` | Không | nodes/edges của input/recipe/output; che node ngoài quyền |
| `/map` | bbox, zoom, drought? | GeoJSON FeatureCollection + display metadata hoặc lỗi bounded |

Mọi response JSON chứa selection_id/release_id và revision; build_id chỉ khi được
read derived. Lookup artifact phải khớp layer, dataset, observation và build selection.
Schema/quality chỉ lộ fields thuộc layer đang xem; không gửi toàn quality.json cho user
chỉ có một layer vì file đó có cả metrics Silver và Gold.

Preview payload tối đa 1 MiB chưa nén, execution budget 5 giây, số rows không vượt limit.
Không trả geometry binary/WKT lớn trong table; schema mô tả geometry riêng.
Cursor preview ràng buộc selection/layer/filter/limit; đảm bảo toàn bộ trang trong
selection dùng cùng immutable artifact. Thay filter xóa cursor, không reset version.

| Layer | Rows/order | Dữ liệu |
|---|---|---|
| Bronze | Member name tăng, từ inventory đã kiểm tra lúc publish | name, extension, size_bytes, sha256; không tự extract ZIP trong request |
| Silver | Ordinal tăng theo Parquet của build; row_id=ordinal | Các scalar fields thực; geometry_type có thể là display field được ghi rõ |
| Gold | grid tăng trong một build | time, grid, lon, lat, drought; query parameter hóa vào gold_cells |

`matched_count` tính trên cùng selection sau filter, không gồm lịch sử; dữ liệu vượt
byte budget không bị cắt im lặng: trả 413 PREVIEW_TOO_LARGE với gợi ý giảm page size.
Quality chưa có thông tin thì `unknown`/null; không tự bịa processed_at từ thời gian
request. Bronze schema là package schema, không giả làm raw DBF scientific schema.

## 6. Map

Silver/Gold read mới dùng được. Bronze trả 422 MAP_NOT_SUPPORTED; capabilities UI
không hiện tab. bbox = west,south,east,north trong WGS84, west < east, south < north;
không xử lý antimeridian ở USDM v1. zoom integer 0–12. drought allowlist 0,D0…D4;
Silver chỉ D0…D4, lọc `0` cho Silver trả 422 vì không có lớp no-drought polygon.

Gold lấy điểm tâm lon/lat, feature ID là grid của build. Silver lấy display geometry
được giản lược/clipped từ đúng artifact; feature ID dựa ordinal. Display cache key
bao gồm release/build/input hash/zoom/filter. Không sửa GeoParquet khoa học.
Response metadata: `geometry_simplified`, `tolerance_degrees` (0 nếu không giản lược),
`feature_count`, selection_id, release_id. UI luôn ghi rõ geometry đã giản lược.

Budget đề xuất: 5 giây, tối đa 5 MiB chưa nén, 5.000 features và 100.000 vertices.
Vượt budget trả 413 MAP_TOO_LARGE yêu cầu zoom/thu hẹp bbox; không drop feature ngầm.
B cần precompute/index display trong bước publish release, không parse toàn bộ
shapefile hoặc chạy cleaner mỗi lần pan bản đồ. Map initial CONUS cho các tuần mẫu
phải đáp ứng budget mới được nghiệm thu.

## 7. Download

`GET /selections/{selection_id}/artifacts/{artifact_id}/download`

- Yêu cầu read + download trên layer của artifact. Chỉ 3 định dạng chính: Bronze ZIP,
  Silver GeoParquet, Gold CSV. Không export SQL/bộ lọc/multi-week ZIP trong Stage 4.
- Trả 200 binary, Content-Type đúng, Content-Disposition attachment tên file được
  sanitize, Content-Length và checksum SHA-256; `X-Content-Type-Options: nosniff`.
- Bytes phải khớp artifact hash trong manifest/registry; giữ nguyên bytes nguồn.
  Kiểm tra integrity trước khi trả headers 200; lỗi trả 503 ARTIFACT_UNAVAILABLE.
- Local resolver chỉ đọc file trong đúng release root, kiểm tra resolve/symlink;
  không dùng filename hay dataset_key từ URL làm path. Artifact ID khác selection
  hoặc layer không được xem trả 404. Không public static mount serving root.
- V1 không cấp public/presigned URL và không range/resume; request Range trả 416.
  Browser nhận qua session cùng origin, không để API key/token ở URL.
- Giới hạn v1: 128 MiB/artifact, 60 giây/request, 2 concurrent downloads/user;
  vượt size trả 413, concurrency trả 429 Retry-After. Hủy stream khi client disconnect.
  File release immutable/read-only; mở và verify cùng file handle trước streaming.
- Audit request, authorization outcome và kết quả stream hoàn tất/hủy; không log
  cookie hoặc signed selector. Không ghi “download completed” trước khi stream kết thúc.

Bounds là giá trị thiết kế để duyệt, cần benchmark tại B. V1 dataset có file lớn hơn
128 MiB không được onboard âm thầm rồi hiển thị nút tải không hoạt động.

## 8. Error/status và bảo vệ tài nguyên

| HTTP | Code ví dụ | UI |
|---|---|---|
| 400 | INVALID_CURSOR | Reset pagination, giữ filter |
| 401 | SESSION_REQUIRED | Login lại |
| 403 | ACTION_FORBIDDEN / CSRF_FAILED | Thông báo thao tác không được phép |
| 404 | RESOURCE_NOT_FOUND | Một thông báo chung cho nonexistent/out-of-scope |
| 409 | LAYER_NOT_BUILT / SELECTION_CONFLICT | Chưa có sản phẩm; không fallback cũ |
| 410 | SELECTION_EXPIRED / RELEASE_EXPIRED | Chọn lại snapshot/current |
| 412 / 428 | VERSION_CONFLICT / PRECONDITION_REQUIRED | Admin tải lại trước khi sửa |
| 413 | PREVIEW_TOO_LARGE / MAP_TOO_LARGE / DOWNLOAD_TOO_LARGE | Thu hẹp request theo hướng dẫn |
| 416 | RANGE_NOT_SUPPORTED | Tải nguyên file |
| 422 | INVALID_FILTER / VERSION_MISMATCH / MAP_NOT_SUPPORTED | Sửa input/capability |
| 429 | RATE_LIMITED | Chờ Retry-After |
| 503 | STORAGE_UNAVAILABLE / ARTIFACT_UNAVAILABLE / PREVIEW_TIMEOUT | Retry giới hạn, request ID |

404/403 không lộ object ngoài quyền qua metadata, count, error text hoặc timing do
đọc storage trước authorize. Server không tự khôi phục DB hoặc gọi ETL khi lỗi đọc.
Proposed per-user limits: 120 metadata requests/phút, 30 preview/map requests/phút,
4 concurrent preview/map requests, cộng giới hạn download. Shared control SQLite
cho accounting Portal trên một node; không làm thay đổi quota collector hiện hữu.
GIS preview worker riêng có memory cap 256 MiB/process và deadline thực; trả lỗi
có kiểm soát khi vượt budget. Không chỉ đặt `limit` UI nhưng backend đọc vô hạn.

## 9. Trace ví dụ (contract, không phải API đang chạy)

1. GET session → role và CSRF; GET datasets → dataset USDM và release_id.
2. GET weeks → chọn 2022-06-28; POST selections current → selection_id + capabilities.
3. GET selection/layers/gold/preview?limit=50 → đúng build, first cursor.
4. GET map cùng selection → đúng tuần/build; GET quality/lineage cùng selection.
5. GET artifact download từ selection → đúng CSV nguyên byte.
6. GET versions → chọn version_id lịch sử → POST selection history mới, banner history.
7. Admin revoke download → GET download cũ trả 403; revoke read → trả 404.
8. Release mới publish giữa bước 3–5 → selection cũ vẫn cùng snapshot, không đổi bytes.
