# Data LakeHouse — Server

Server nhận file từ Client qua FastAPI, kiểm tra SHA-256, lưu raw vào MinIO Bronze và quản lý observation/revision bằng SQLite.

Repo tương ứng: [Client](https://github.com/phamquocanh149/IT5425_DataLakeHouse_Client).

```text
Máy Client: HTTPX + hàng đợi
    │ HTTPS /upload + X-API-Key
    ▼
Máy Server: FastAPI → MinIO Bronze
                  └→ SQLite trên persistent volume
```

Chỉ Bronze hoạt động thật. Silver, Gold và Warehouse được tạo sẵn, chưa có ETL. Client không truy cập MinIO trực tiếp; GitHub chứa code, không trung chuyển dữ liệu.

## 1. Chuẩn bị và clone

Cần Git, Docker Engine chạy **Linux/amd64**, Docker Compose từ **2.24.4**. Trên Windows dùng Docker Desktop với Linux containers. Windows Server OS cần Docker Engine/Compose trong máy ảo Linux. Python 3.11 chỉ cần cho công cụ native và tests, không bắt buộc khi chạy toàn bộ Server bằng Docker.

Các lệnh bên dưới dùng PowerShell:

```powershell
git clone https://github.com/phamquocanh149/IT5425_DataLakeHouse_Server.git climate-platform
cd climate-platform
docker version
docker compose version
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Nếu đã có checkout/dữ liệu, giữ nguyên `.env` và tên Compose project. Không tạo project mới rồi hiểu nhầm volume mới trống là mất dữ liệu.

## 2. Điền cấu hình `.env`

Điền đủ sáu biến sau bằng credentials riêng, không để trống:

| Biến | Giá trị cần thiết |
|---|---|
| `COLLECTOR_API_KEY` | Khóa upload; gửi riêng cho người chạy Client |
| `ADMIN_API_KEY` | Khóa quản trị API, khác collector; không cấp cho Client |
| `MINIO_ROOT_USER` | Tên quản trị MinIO, ví dụ `climate-admin` |
| `MINIO_ROOT_PASSWORD` | Mật khẩu root mạnh, ngẫu nhiên |
| `S3_ACCESS_KEY` | Tên ingestion riêng do bạn đặt; khác root |
| `S3_SECRET_KEY` | Mật khẩu ingestion ngẫu nhiên, khác mật khẩu root |

Giữ `STORAGE_BACKEND=s3`, tên bốn bucket và hai digest image trong `.env.example`. Endpoint `http://127.0.0.1:9000` dùng cho công cụ native; Compose tự đặt `http://minio:9000` cho API.

Có thể tạo từng khóa bằng PowerShell và lưu kết quả vào `.env`:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
[Convert]::ToBase64String($bytes)
$rng.Dispose()
```

Chạy lại để tạo các khóa khác nhau. Không commit `.env` hoặc chia sẻ log/ảnh chứa secrets. Biến môi trường hệ điều hành có thể ghi đè `.env`.

## 3. Khởi động Server và MinIO

```powershell
docker compose up -d --build --wait --wait-timeout 120
docker compose ps -a
Invoke-RestMethod http://127.0.0.1:8000/health
```

Mong đợi: `api`, `minio` healthy; `minio-init` Exited với mã 0. Init chạy một lần nên Exited 0 là bình thường.

| Địa chỉ trên máy Server | Chức năng |
|---|---|
| http://127.0.0.1:8000/health | API liveness |
| http://127.0.0.1:8000/docs | Tài liệu API |
| http://127.0.0.1:9000 | S3 endpoint |
| http://127.0.0.1:9001 | MinIO Console; đăng nhập bằng root trong `.env` |

Console phải có bốn bucket private, có versioning: `climate-bronze`, `climate-silver`, `climate-gold`, `climate-warehouse`. `/health` chưa chứng minh upload/checksum đã thành công.

```powershell
docker compose logs --tail 100 api minio minio-init
docker compose exec -T api python scripts/reconcile_storage.py --checksum
```

## 4. Kết nối hai máy bằng VS Code Dev Tunnels

Mặc định API chỉ bind `127.0.0.1:8000`, nên máy khác không truy cập trực tiếp. Để demo khác mạng mà không cài Tailscale:

1. Trên máy Server, mở cửa sổ VS Code local, giữ Docker đang chạy.
2. Mở tab **Ports**; có thể dùng Command Palette: `Ports: Focus on Ports View`.
3. Chọn **Forward a Port**, nhập `8000`, đăng nhập theo yêu cầu.
4. Sao chép URL HTTPS trong **Forwarded Address**.
5. Với Client HTTPX hiện tại, chọn **Port Visibility → Public** nếu chấp nhận công khai endpoint API cho demo.
6. Gửi riêng URL và `COLLECTOR_API_KEY` cho người chạy Client.

Cổng Private yêu cầu thêm xác thực tunnel. Header `X-API-Key` không thay thế xác thực đó; Client hiện chưa hỗ trợ đăng nhập Dev Tunnels. Public bỏ đăng nhập tunnel, nhưng `/upload` vẫn kiểm tra API key. Không cần chia sẻ tài khoản GitHub.

Trên Client:

```dotenv
SERVER_BASE_URL=https://<dia-chi-forward-duoc-cap>
SERVER_API_KEY=<COLLECTOR_API_KEY-cua-server>
```

Không thêm `/upload` vào URL gốc. Chỉ forward **8000**, không forward **9000/9001**. Giữ nguyên bind loopback của Compose. Kiểm tra `<URL>/health` trả JSON của API, không phải trang đăng nhập HTML.

Máy Server, Docker và phiên tunnel cần hoạt động; tránh sleep. Nếu URL thay đổi, sửa `.env` Client và khởi động lại worker. Tunnel có giới hạn băng thông/dịch vụ, phù hợp demo hơn là pipeline lớn liên tục.

**Remote-SSH là cách khác:** máy Client phải SSH được tới Server trước rồi forward cổng remote 8000 về cổng local được VS Code cấp. Remote-SSH không tự giải quyết việc hai máy khác mạng/NAT. Có thể sử dụng VPN hoặc HTTPS reverse proxy thay tunnel.

Tham khảo: [VS Code Port Forwarding](https://code.visualstudio.com/docs/debugtest/port-forwarding), [Remote-SSH](https://code.visualstudio.com/docs/remote/ssh).

## 5. Gửi file và kiểm tra

Làm theo [README Client](https://github.com/phamquocanh149/IT5425_DataLakeHouse_Client#readme): kiểm tra kết nối, tạo mẫu, chạy `send_file.py`.

- `VERIFIED`: object đã upload và download kiểm tra SHA-256/kích thước, SQLite đã commit.
- `DUPLICATE`: observation và nội dung đã tồn tại, được xác minh; không tạo observation mới.
- Cùng source/ngày/dataset key nhưng nội dung thay đổi: tạo revision, giữ raw cũ.
- Ngày `source_date` là ngày khoa học của dữ liệu, không phải ngày gửi file.

```text
climate-bronze/source=usdm/year=2021/date=2021-06-22/dataset=<hash-dataset-key>/revision=1/sha256=<hash-noi-dung>/raw.csv
```

API giữ field `file`, `source`, `source_date`, optional `dataset_key` và header `X-API-Key`. Dataset key nên ổn định theo sản phẩm/trạm/chỉ tiêu; mặc định là tên file. Xem [API contract](docs/API_CONTRACT.md).

## 6. Dừng và bảo toàn dữ liệu

```powershell
docker compose stop
docker compose start
# Xóa container/network nhưng giữ named volumes:
docker compose down
docker compose up -d --wait
```

**Không chạy `docker compose down -v` hoặc prune volume chứa dữ liệu.** Volume `minio-data` chứa object; `registry` chứa SQLite; `bronze` cũ giữ temp/raw legacy. Giữ cùng tên Compose project khi chạy lại. SQLite/DuckDB đang ghi phải nằm trên storage local/block phù hợp, không trực tiếp trên S3.

## 7. Migration, backup và phục hồi

Dữ liệu native không tự xuất hiện trong Docker volume. Xem [hướng dẫn migration/backup/restore](docs/MINIO_OPERATIONS.md), gồm import legacy checkout, dry-run, backup SQLite, sao lưu MinIO và rollback.

Nếu raw/metadata cũ đã nằm trong Docker volume và MinIO đã được khởi tạo:

```powershell
docker compose stop api
docker compose run --rm --no-deps api python scripts/migrate_metadata.py
docker compose run --rm --no-deps api python scripts/migrate_bronze_s3.py --dry-run
# Chỉ apply sau khi inventory đúng và không có lỗi:
docker compose run --rm --no-deps api python scripts/migrate_bronze_s3.py --apply
docker compose run --rm --no-deps api python scripts/reconcile_storage.py --checksum
docker compose up -d --wait
```

Migration giữ file/JSON cũ, backup SQLite trước khi cập nhật mapping. Orphan chỉ được báo cáo, không tự xóa. Thêm `--repair-status` vào lệnh reconcile để cập nhật trạng thái sau kiểm tra. Backup dài hạn cần nằm ngoài volume đang vận hành; copy SQLite đang ghi mà bỏ WAL không phải backup nhất quán.

## 8. Kiểm thử

Clone Client vào `climate-collector` cạnh `climate-platform`, hoặc đặt `CLIENT_REPO_PATH` tới checkout Client.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/compose_smoke.py
```

Smoke dùng project, bucket, registry và credentials riêng để kiểm tra Client thật → API → MinIO, revision/duplicate, outage/retry và persistence. Nó dừng container test nhưng giữ named volumes test để kiểm tra. Đây chưa phải kiểm thử hai máy vật lý. CI chạy lint/tests/build/smoke, không deploy hoặc dùng secrets production.

## 9. Xử lý lỗi

| Hiện tượng | Cách kiểm tra |
|---|---|
| Không kết nối Docker daemon | Mở Docker Desktop, xác nhận Linux containers và quyền Docker |
| Compose báo thiếu biến | Điền đủ credentials ở mục 2 trong đúng `.env` |
| HTTP 401 | So sánh khóa Client với `COLLECTOR_API_KEY` Server |
| HTTP 403 | Kiểm tra quyền source/ownership; không dùng admin key upload |
| HTTP 413 | File vượt giới hạn mặc định 20 MiB |
| HTTP 503 | Kiểm tra MinIO và reconciliation; không tự fallback local |
| Tunnel trả HTML/302 | Kiểm tra Private/Public và URL; Client không đăng nhập tunnel |
| Client khác máy dùng localhost | Đổi sang HTTPS tunnel; localhost chỉ chính máy Client |

## 10. Trạng thái và giới hạn

[Báo cáo tích hợp](MINIO_INTEGRATION_REPORT.md) ghi digest, kết quả test và migration tại môi trường triển khai. Hai image bên thứ ba bắt buộc có CVE High/Critical và chưa xác minh chuỗi chữ ký nguồn gốc. Kết quả chức năng PASS không có nghĩa hệ thống đã được chấp thuận an toàn production. Xem [scan MinIO](docs/security/minio-cves.md), [scan mc](docs/security/mc-cves.md).

Collector hiện còn là khung tích hợp; dữ liệu mẫu chỉ dùng thử truyền file, không phải bộ dữ liệu khoa học đã kiểm định.
