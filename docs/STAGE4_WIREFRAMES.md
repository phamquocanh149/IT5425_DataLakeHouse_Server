# Stage 4 — Wireframes v1

**Design approved.** Đây là wireframe baseline; frontend đã được triển khai local,
xem [runbook](STAGE4_IMPLEMENTATION.md). Bản dưới đây không phải frontend
đã chạy. Đọc cùng [thiết kế](STAGE4_DESIGN.md) và [API contract](STAGE4_API_CONTRACT.md).
Các số trong mock là baseline Stage 3 hoặc ký hiệu minh họa, UI thực phải lấy API.

## W1 — Login `/portal/login`

```text
+------------------------------------------------------------------+
|                      CLIMATE DATA PORTAL                         |
|          Xem dữ liệu khí hậu và tải sản phẩm phân tích             |
|                                                                  |
|                 [ Đăng nhập bằng tài khoản tổ chức ]              |
|                                                                  |
|           Bạn chỉ thấy dữ liệu đã được cấp quyền.                 |
|           Không có quyền truy cập? Liên hệ quản trị viên.          |
+------------------------------------------------------------------+
```

Nhập username/password cục bộ trong Portal; không nhập API key hoặc mật khẩu MinIO.
Đăng nhập xong trở lại internal route đã yêu cầu, không cho open redirect ra ngoài.
Đã login nhưng chưa được grant: vào Overview với hướng dẫn xin cấp quyền.
Sai credentials: thông báo “Chưa thể đăng nhập”, nút thử lại, request ID; không lộ chi tiết.

## W2 — Overview `/portal`

```text
+------------------------------------------------------------------+
| Climate Data Portal         Snapshot: <as_of>     <Tên> <Vai trò> ▾ |
+---------------+--------------------------------------------------+
| Tổng quan     | Tổng quan dữ liệu                                |
| Danh mục      | [Nguồn: Tất cả ▾]                                |
|               |                                                  |
|               | Dataset được xem | Tuần có Gold | Gold rows       |
|               |        1         |     130      |   423.670       |
|               |                                                  |
|               | USDM / CONUS                                     |
|               | Phạm vi: 07/01/2020 – 28/06/2022                  |
|               | Bronze [Đã xác minh] Silver [Đạt] Gold [Sẵn sàng]  |
|               | [Mở danh mục]                                    |
|               |                                                  |
|               | Chú ý: dữ liệu historical, không phải feed live.  |
+---------------+--------------------------------------------------+
```

Counts chỉ trong quyền người dùng; không được suy số dataset ngoài grant. Một layer
không có quyền không hiện count/quality của layer đó. Không dùng một “chấm xanh hệ
thống” để thay chất lượng dữ liệu; tuổi snapshot và phạm vi quan sát tách biệt.
Operator/Admin có khối “Lịch sử xử lý đã ghi nhận” theo snapshot và dataset được xem,
không có nút Run/Retry/Cancel, không phần trăm tiến độ hoặc heartbeat giả.

## W3 — Catalog `/portal/catalog`

```text
+------------------------------------------------------------------+
| Climate Data Portal          Snapshot: <as_of>           <User> ▾  |
+---------------+--------------------------------------------------+
| Tổng quan     | Danh mục dữ liệu                                 |
| Danh mục      | [Tìm tên dataset...] [Nguồn ▾] [Layer ▾]            |
|               | [Từ ngày] [Đến ngày] [Áp dụng] [Xóa bộ lọc]        |
|               |                                                  |
|               | Dataset      Phạm vi        Layer được xem       |
|               | USDM CONUS   2020 – 2022    Bronze Silver Gold    |
|               | [Chọn tuần]                                      |
|               |                                                  |
|               | Tuần          Bronze      Silver     Gold         |
|               | 28/06/2022    Verified    Available  Available    |
|               | 21/06/2022    Verified    Available  Available    |
|               | ...                                              |
|               | [Trước]  25 tuần/trang  [Tiếp]                    |
+---------------+--------------------------------------------------+
```

Chọn dataset mở danh sách tuần có phân trang; chọn tuần vào Dataset Detail, mặc định
layer đầu tiên được cấp quyền theo thứ tự Bronze → Silver → Gold. Link từ một layer
cụ thể giữ layer đó. Bộ lọc ngày là ngày quan sát, không phải thời gian job chạy.
Không render nguồn chưa onboard như nguồn có dữ liệu. Tìm không thấy trả empty state,
không báo lỗi backend. URL giữ nguồn/dataset/tuần/layer, Back giữ vị trí/bộ lọc.

## W4 — Dataset Detail `/portal/datasets/:dataset_id/weeks/:week`

```text
+----------------------------------------------------------------------+
| Climate Data Portal             Snapshot: <as_of>           <User> ▾   |
+---------------+------------------------------------------------------+
| Tổng quan     | Danh mục > USDM > CONUS > 28/06/2022                  |
| Danh mục      | [Tuần ▾] [Hiện hành tại snapshot ▾]   [Tải ZIP/Parquet/CSV]|
|               | Revision <n>   Build <rút gọn>   Chất lượng <status>  |
|               |                                                      |
|               | [ BRONZE ]   [ SILVER ]   [ GOLD ]                   |
|               |                                                      |
|               | [Dữ liệu] [Bản đồ] [Schema] [Quality] [Lineage]       |
|               | [Lịch sử phiên bản]                                  |
|               |                                                      |
|               | <Nội dung layer + chế độ đang chọn>                  |
|               |                                                      |
|               | [Trước] [50 dòng/trang ▾] [Tiếp]                      |
+---------------+------------------------------------------------------+
```

Hai cấp tab có ý nghĩa khác nhau: layer chọn sản phẩm; chế độ chọn cách xem cùng
sản phẩm. Tab ngoài quyền bị ẩn. Khi không có build, layer được quyền vẫn hiện nhưng
hiển thị “Chưa có sản phẩm cho revision này”; download disabled kèm lý do.
Nút tải ghi rõ định dạng, dung lượng, tuần và phiên bản. Download nguyên artifact,
không ngụ ý xuất riêng những dòng đang lọc. Bảng tối đa 200 rows/trang theo contract.

### W4.1 — Bronze: danh sách thành phần raw

```text
Package: USDM_20220628_M.zip     Size: <bytes>    SHA-256: <rút gọn>
Trạng thái: Bytes đã xác minh — chưa phải kết luận chất lượng khoa học

File                 Định dạng   Kích thước     SHA-256
USDM_20220628.shp     SHP         <...>         <...>
USDM_20220628.dbf     DBF         <...>         <...>
USDM_20220628.shx     SHX         <...>         <...>
USDM_20220628.prj     PRJ         <...>         <...>
...
```

Bronze preview v1 là metadata và inventory nguyên gói; không parse/hiển thị raw polygon
hoặc bảng DBF. Tab Bản đồ không có ở Bronze; gợi ý xem Silver nếu có quyền. Schema
Bronze mô tả transport package và sidecar, không gán schema Silver cho raw. Tải toàn
ZIP bytes gốc đã đăng ký, không tải từng member hoặc giải nén tùy ý trên Server.

### W4.2 — Silver: bảng polygon và schema

```text
week_date  time_id   dm_value  drought_category  source_object_id  repaired
<date>     <time>    0         D0                <id>              true
...
CRS: EPSG:4326     Geometry: Polygon/MultiPolygon     Features: <count>
```

Bảng hiển thị các cột có thật trong Parquet, không dump WKB/geometry lớn vào JSON.
Schema có type, nullable, ý nghĩa; `shape_area` nguồn chưa chứng minh đơn vị nên ghi
“Đơn vị nguồn chưa xác minh”, không gọi là km². Identifier phục vụ phân trang là
ordinal trong artifact bất biến, không giả định `source_object_id` unique.

### W4.3 — Gold: bảng grid

```text
[Nhãn hạn hán: Tất cả ▾] [Mã grid...] [Áp dụng]
time       grid     lon       lat       drought
<time>     <grid>   <lon>     <lat>     D2
...
0 = Không hạn; D0 = Khô bất thường; D1–D4 = các mức hạn hán.
```

Một dòng cho `(build_id, grid)`; count trong preview là count sau lọc của đúng build.
Không cộng các tuần/build lịch sử vào tổng rows của tuần đang xem.

### W4.4 — Bản đồ

```text
[Tuần <date>] [Silver polygons | Gold grid centers] [Mức hạn ▾]
+--------------------------------------------------------+
|                   Bản đồ CONUS                         |
|   Pan / Zoom          Click → thuộc tính đối tượng      |
|                                                        |
|   Chú giải: 0  D0  D1  D2  D3  D4                      |
+--------------------------------------------------------+
Snapshot <as_of> / Revision <n> / Build <id>
Hình học hiển thị đã rút gọn; tải Parquet để lấy hình học đầy đủ.
```

Silver vẽ polygon đã giản lược cho hiển thị; Gold vẽ tâm grid thật lon/lat, không tự
tạo polygon “diện tích hạn” từ điểm. Màu có text label, tooltip và bảng tương đương.
Đổi layer không giữ tooltip từ build cũ. Request theo viewport/zoom có giới hạn;
không tự tải tất cả tuần. Khi vượt giới hạn yêu cầu zoom/lọc, không âm thầm bỏ đối tượng.
Map layer không thuộc quyền không được gửi xuống browser dù bị ẩn bằng CSS.
Đề xuất MapLibre cho B theo [tài liệu chính thức](https://maplibre.org/maplibre-gl-js/docs/).
Basemap cần attribution và nguồn được phép; nếu không cấu hình, vẫn có nền CONUS tối
giản/khung tọa độ và dữ liệu, không phụ thuộc demo tiles để nghiệm thu.

### W4.5 — Quality, lineage và history

Quality phân biệt transport verification với scientific validation. Silver hiện raw/
silver feature counts, repairs, quarantine; Gold hiện tổng grid và phân bố nhãn. Không
hiện “accuracy 100%” như chỉ số phổ quát: đối chiếu 100% là bằng chứng checkpoint Stage 3.

```text
Lineage:
Bronze file_id / revision / hash
   → Recipe (cleaner + worker + library versions + grid reference hash)
   → Build
   → Silver artifact hash → Gold artifact hash

History:
Revision  Build        Completed at      Snapshot current    [Xem]
<n>       <build-A>    <timestamp>       Có                  [Xem]
<n>       <build-B>    <timestamp>       Không               [Xem]
<n-1>     <build-C>    <timestamp>       Không               [Xem]
```

Lineage trình bày raw → build tạo Silver → Gold từ Silver; recipe/reference là
dependency, không gợi ý Gold đọc raw trực tiếp. Node ngoài quyền chỉ ghi “Nguồn phụ
thuộc bị giới hạn”, không lộ ID/path/hash. Không có nút promote/rollback/delete.
Chọn history hiện banner “Đang xem lịch sử”, có nút về current. Download pin đúng
history đang xem. Operator/Admin có panel attempts readonly với thông báo lỗi đã
lọc secrets/paths, không trình bày raw stderr từ worker.

## W5 — Drawer quyền (Admin, từ menu user)

```text
Quản lý quyền                                      [Đóng]
[Tìm người dùng đã đăng nhập...]
User: <display_name>         Role: [Viewer ▾]
Dataset: [USDM CONUS ▾]
          Read     Download
Bronze     [ ]       [ ]
Silver     [x]       [ ]
Gold       [x]       [x]
[Lưu thay đổi] [Hủy]
```

Xem thay đổi trước khi lưu; không tạo account/mật khẩu. Có version conflict khi Admin
khác sửa đồng thời; tải lại quyền thay vì ghi đè mù. Admin không được tự hạ role hoặc
vô hiệu hóa Admin cuối cùng. Giao diện xác nhận quyền lưu từ response, không chỉ toast.

## W6 — Trạng thái dùng chung

| Tình huống | Cách hiển thị / hành động |
|---|---|
| Loading | Skeleton đúng khu vực; không hiển thị số 0 giả, không để dữ liệu tuần cũ dưới nhãn tuần mới |
| Không có grant | “Chưa được cấp dữ liệu”; không lộ dataset count |
| Không có kết quả lọc | “Không tìm thấy dữ liệu”; nút xóa bộ lọc |
| Chưa có Silver/Gold | “Chưa có sản phẩm cho revision này”; không fallback lịch sử |
| History | Banner lịch sử + revision/build + quay về current |
| Snapshot cũ | Ghi thời điểm snapshot; gợi ý tải bản mới khi active release đổi |
| 401 | Xóa state/cache nhạy cảm trong UI; login lại; giữ internal destination |
| 403 / 404 | Không đủ quyền thao tác / dữ liệu không khả dụng; không lộ paths |
| 410 | Lựa chọn hết hiệu lực; nút tải lại current, không tải nhầm file mới tự động |
| 413 map / 422 filter | Hướng dẫn thu hẹp viewport hoặc sửa bộ lọc |
| 429 | Thời gian chờ theo Retry-After; không loop request liên tục |
| 503 / lỗi mạng | Thử lại có giới hạn + request ID; giữ filter, không ghi “0 rows” |

Desktop sidebar; mobile sidebar thu gọn, table cuộn ngang, map đổi sang tab riêng.
Keyboard focus rõ, label đầy đủ, trạng thái có chữ/icon ngoài màu. Số liệu định dạng
theo locale; ISO date trong API, ngày quan sát không đổi theo timezone; timestamp chạy
hiển thị Asia/Saigon kèm timezone. Bỏ mọi nút upload/run/retry/cancel/SQL khỏi v1.
