> P0.4/P0.5 remediation: see [readiness, credentials, TLS and deployment prerequisites](docs/security.md).
> `/readyz` is readiness; `/livez` is liveness; `/health` remains a readiness alias.
> Release verification requires digest-pinned self-built MinIO images (`MINIO_IMAGE`, `MINIO_MC_IMAGE`).

﻿# Data LakeHouse — Server

Server nhận file từ Client qua FastAPI, kiểm tra SHA-256, lưu raw vào MinIO Bronze và quản lý observation/revision bằng SQLite.

Repo tương ứng: [Client](https://github.com/phamquocanh149/IT5425_DataLakeHouse_Client).

```text
Máy Client: HTTPX + hàng đợi
    │ HTTPS /upload + X-API-Key
    ▼
Máy Server: FastAPI → MinIO Bronze
                  └→ SQLite trên persistent volume
```

Stage 3 đã có USDM Bronze → Silver GeoParquet → Gold CSV/SQLite local.
Stage 4 có Portal React/TypeScript + FastAPI để xem/tải ba tầng, bản đồ, quality,
lineage, current/history và quản lý quyền. Demo: **http://127.0.0.1:8010/portal/**.
Xem [hướng dẫn demo và vận hành](docs/STAGE4_IMPLEMENTATION.md),
[checklist nghiệm thu](docs/STAGE4_ACCEPTANCE.md). Stage 4 đang chờ user UAT,
chưa Completed. Client không truy cập MinIO trực tiếp; GitHub chứa code, không trung chuyển dữ liệu.

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

### Một file Compose cho mọi cách chạy

Chỉ dùng `compose.yaml`; chọn image và xác thực qua `.env` hoặc biến môi trường:

| Cách chạy | Cấu hình | Lệnh |
|---|---|---|
| MinIO tự build (khuyến nghị, qua gate release) | `MINIO_IMAGE=noname12346767/my-minio@sha256:...`, `MINIO_MC_IMAGE=noname12346767/mc-allos@sha256:...`; API build từ source | `docker compose up -d --build` |
| MinIO tự build chỉ có trên máy (chưa push) | `MINIO_IMAGE=noname12346767/my-minio`, `MINIO_MC_IMAGE=noname12346767/mc-allos`, `MINIO_PULL_POLICY=never` | `docker compose up -d --build` |
| Image demo có sẵn | Đặt `CLIMATE_API_IMAGE`, `MINIO_IMAGE`, `MINIO_MC_IMAGE` theo image đã chọn; `API_PULL_POLICY=never`, `MINIO_PULL_POLICY=never` | `docker compose up -d --no-build` |
| Internet qua Nginx/TLS | Chọn image như trên; thêm `ENABLE_STATIC_KEYS=false` và `API_KEYS` chứa key records hợp lệ | `docker compose up -d` |

`compose.yaml` chạy đúng hai image trong `MINIO_IMAGE`/`MINIO_MC_IMAGE`, cũng là hai
image mà `scripts/release/verify_images.py` kiểm định. Vì vậy gate bảo vệ đúng thứ
thực sự chạy. Chỉ dùng image MinIO do bạn tự build (`noname12346767/my-minio`,
`noname12346767/mc-allos`); không trỏ sang image của nhà phát hành khác như
`quay.io/minio/*` hay `minio/*`. Gate yêu cầu pin theo `@sha256:`; image local/demo
phải tồn tại trước khi chạy và không được coi là đã qua gate release. Với project
đang tồn tại, tiếp tục dùng đúng `-p <tên-project-cũ>`; giữ nguyên `bronze`, `registry`,
`minio-data`. Không cần xóa hoặc tạo lại volumes khi chuyển sang file hợp nhất.

### Cấu trúc package và lệnh chạy (Phase 1)

Toàn bộ backend Python là một package cài đặt được: `src/climate_platform/`.

```text
src/climate_platform/
  app.py               # AppModule: composition root (uvicorn target)
  config.py            # Pydantic Settings tập trung
  cli.py               # console entry points
  common/              # errors.py, middleware.py, pipes.py, interceptors.py
  modules/             # feature modules (controller/service/repository/dto)
    system/            # /livez /readyz /health + readiness
    auth/              # authentication + session
    authorization/     # guards/policy/grants
    ingestion/         # service.py, validation.py, controller.py
    storage/           # object store repository (MinIO/S3 + local)
    catalog/           # registry SQLite, service, maintenance
    processing/        # contracts.py, engine.py, publisher.py
    portal/            # controllers/, services/, repositories/, workers/
  datasets/usdm/       # processor.py, science.py, resources/
```

Lệnh chạy sau `python -m pip install .` (thêm `[portal]` nếu bật Portal).
Editable install `python -m pip install -e .` dùng cho phát triển; trên Python 3.11
Windows, setuptools có thể lỗi encoding nếu đường dẫn chứa tiếng Việt. Khi đó dùng
cài đặt thường hoặc wheel. Kết quả kiểm chứng và các gate còn mở nằm trong
[Phase 1 closeout](docs/PHASE1_CLOSEOUT.md).

```powershell
uvicorn climate_platform.app:app --host 127.0.0.1 --port 8000       # API
climate-usdm-replay --source-root <src> --output-root <out> --gis-python <py>
python -m climate_platform.datasets.usdm.science --help             # GIS worker
```

`STAGING`/`PRODUCTION` không được tuyên bố production-ready khi Phase 2/3 (Postgres, S3-first Silver/Gold) chưa hoàn tất.

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

`STORAGE_BACKEND=s3`, tên bốn bucket và các giới hạn vận hành khác đã được hardcode làm giá trị mặc định trong `src/climate_platform/config.py` (và `compose.yaml`), không cần khai báo trong `.env`; chỉ hai tham chiếu image MinIO tự build (`MINIO_IMAGE`, `MINIO_MC_IMAGE`) cần điền trong `.env.example`. Endpoint `http://127.0.0.1:9000` dùng cho công cụ native; Compose tự đặt `http://minio:9000` cho API.

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
| http://127.0.0.1:8000/livez | API liveness |
| http://127.0.0.1:8000/readyz | Dependency readiness (200/503) |
| http://127.0.0.1:8000/docs | Tài liệu API |
| http://127.0.0.1:9000 | S3 endpoint |
| http://127.0.0.1:9001 | MinIO Console; đăng nhập bằng root trong `.env` |

Console phải có bốn bucket private, có versioning: `climate-bronze`, `climate-silver`, `climate-gold`, `climate-warehouse`. `/health` chưa chứng minh upload/checksum đã thành công.

```powershell
docker compose logs --tail 100 api minio minio-init
docker compose exec -T api python scripts/migration/reconcile_storage.py --checksum
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

**Stage 2 — fix lỗi:** [runbook S3 duy nhất](docs/MINIO_OPERATIONS.md#backup-and-restore)
bao gồm SQLite `.backup()`, snapshot **toàn volume MinIO đã dừng**, manifest/checksum
và restore vào volumes mới. `docs/STORAGE_OPERATIONS.md` chỉ dành cho legacy local;
backup hai volume API không chứa đủ object S3. RPO mục tiêu <=24h, RTO mục tiêu <=2h;
backup hằng ngày/drill hằng tháng cần được operator cấu hình và đo nghiệm thu.
Tiến độ chi tiết, phần DONE và Needs Verification: [AGENT.md](AGENT.md#stage-2--fix-lỗi-và-củng-cố-hệ-thống-còn-gate-vận-hành).


Dữ liệu native không tự xuất hiện trong Docker volume. Xem [hướng dẫn migration/backup/restore](docs/MINIO_OPERATIONS.md), gồm import legacy checkout, dry-run, backup SQLite, sao lưu MinIO và rollback.

Nếu raw/metadata cũ đã nằm trong Docker volume và MinIO đã được khởi tạo:

```powershell
docker compose stop api
docker compose run --rm --no-deps api python scripts/migration/migrate_metadata.py
docker compose run --rm --no-deps api python scripts/migration/migrate_bronze_s3.py --dry-run
# Chỉ apply sau khi inventory đúng và không có lỗi:
docker compose run --rm --no-deps api python scripts/migration/migrate_bronze_s3.py --apply
docker compose run --rm --no-deps api python scripts/migration/reconcile_storage.py --checksum
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
.\.venv\Scripts\python.exe scripts/smoke/compose_smoke.py
```

Smoke dùng project, bucket, registry và credentials riêng để kiểm tra Client thật → API → MinIO, revision/duplicate, outage/retry và persistence. Nó dừng container test nhưng giữ named volumes test để kiểm tra. Đây chưa phải kiểm thử hai máy vật lý. Repo không dùng CI/CD; lint/tests/build/smoke chạy local, không deploy hoặc dùng secrets production.

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

[Báo cáo tích hợp](MINIO_INTEGRATION_REPORT.md) ghi digest, kết quả test và migration tại môi trường triển khai. Hai image MinIO tự build cần được gate release scan vì có thể chứa CVE High/Critical. Kết quả chức năng PASS không có nghĩa hệ thống đã được chấp thuận an toàn production. Xem [scan MinIO](docs/security/minio-cves.md), [scan mc](docs/security/mc-cves.md).

Collector hiện còn là khung tích hợp; dữ liệu mẫu chỉ dùng thử truyền file, không phải bộ dữ liệu khoa học đã kiểm định.

## Stage 5 — Checkpoint và phục hồi

Đã thêm checkpoint toàn pipeline (Bronze, registry, products, warehouse và recipe),
restore vào root độc lập, GIS test bắt buộc chạy local, worker image và scan/SBOM
cho API/worker/MinIO/mc. Xem [runbook và gate nghiệm thu](docs/STAGE5_PRODUCTION_READINESS.md).
Local tests/drill đã đạt; MinIO thật, Docker, off-host và service RPO/RTO
còn chờ nghiệm thu. Repo không dùng CI/CD. Visualization/dashboard không thuộc thay đổi Stage 5.
