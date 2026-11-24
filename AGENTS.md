# AGENTS.md — Rules và convention / Server climate-platform

Cập nhật: 2026-11-23 (Asia/Saigon). Repo này là **Server**; Client là `../climate-collector`.

File này chỉ giữ **rules/convention** để làm việc trong repo. Plan, roadmap và tiến độ từng stage
đã chuyển sang thư mục `.agents/plans/`. Không viết tiến độ/task vào file này.

## CI/CD — không sử dụng

- **Không thêm GitHub Actions, workflow, pipeline CI/CD hoặc dịch vụ CI** (GitLab CI, Jenkins,
  Azure Pipelines, CircleCI, v.v.) vào repo này.
- Không tạo/cập nhật `.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile` hoặc cấu hình CI/CD
  tương đương.
- Mọi kiểm tra lint/test/build/smoke chạy local bằng lệnh trong tài liệu của repo.
- Không dựa vào CI để đóng gate/acceptance; bằng chứng phải là kết quả chạy local có command,
  ngày và artifact tương ứng. Ghi chú CI trong tài liệu lịch sử chỉ là lịch sử, không được dùng
  để khôi phục pipeline.

## Plan và roadmap

- **[Plan chính](.agents/plans/AGENT.md)** — index plan, quy ước trạng thái, tổng quan stage.
- Stage: [1 Baseline](.agents/plans/STAGE_1_BASELINE.md) ·
  [2 Hardening](.agents/plans/STAGE_2_HARDENING.md) ·
  [3 USDM](.agents/plans/STAGE_3_USDM.md) ·
  [4 Portal](.agents/plans/STAGE_4_PORTAL.md) ·
  [5 Checkpoint](.agents/plans/STAGE_5_CHECKPOINT.md) ·
  [6 Operations](.agents/plans/STAGE_6_OPERATIONS.md)
- **[Backlog](.agents/plans/BACKLOG.md)** — việc đã ghi nhận nhưng chưa sửa.
- Chỉ đọc plan để biết tiến độ; roadmap **không** cấp quyền triển khai stage tiếp theo, deploy,
  rotate secrets, apply retention hoặc cài dependency. Chỉ làm stage/task người dùng đã giao.

## Cấu trúc repo

- Cây thư mục chính (bỏ qua cache, môi trường ảo, dependency cài sẵn và artifact sinh ra):

  ```text
  climate-platform/
  ├── .agents/
  │   ├── plans/                 # Roadmap và trạng thái các stage
  │   ├── skills/                # Hướng dẫn riêng của repo
  │   └── temp/                  # Bắt buộc: mọi file/thư mục tạm để ở đây
  ├── data_lake/                 # Dữ liệu runtime; bảo toàn dữ liệu hiện có
  ├── deploy/                    # Cấu hình triển khai, ví dụ nginx.conf
  ├── docs/                      # Tài liệu; security/ chứa tài liệu bảo mật
  ├── metadata/                  # Metadata runtime
  ├── scripts/                   # Công cụ vận hành, smoke test và migration
  │   ├── backup/                # Backup/restore checkpoint và recovery drill
  │   ├── migration/             # Migration, import và reconcile storage
  │   ├── ops/                   # Công cụ vận hành thủ công và init MinIO
  │   ├── portal/                # Demo, publish và benchmark Portal
  │   ├── process_data/          # CLI xử lý dữ liệu theo batch
  │   │   ├── nldas/             # NLDAS Bronze -> Silver -> Gold medallion
  │   │   └── usdm/              # CLI replay/verify USDM
  │   ├── release/               # Gate release: GIS report và image scan
  │   └── smoke/                 # Smoke test và fault assertions
  ├── src/climate_platform/      # Backend Python, package cài được (không còn server/)
  │   ├── app.py                 # AppModule: composition root (uvicorn target)
  │   ├── config.py              # ConfigModule: Settings/.env
  │   ├── cli.py                 # Console entry points
  │   ├── common/                # Cross-cutting: errors, middleware, pipes, interceptors
  │   ├── modules/               # Feature modules (controller/service/repository/dto)
  │   │   ├── system/            # /livez /readyz /health + readiness probe
  │   │   ├── auth/              # Authentication + session
  │   │   ├── authorization/     # Phân quyền (guards/policy/grants)
  │   │   ├── ingestion/         # Validation và luồng ingest → Bronze
  │   │   ├── storage/           # Object storage repository (MinIO/S3 + local Bronze)
  │   │   ├── catalog/           # Registry SQLite + maintenance/reconcile
  │   │   ├── processing/        # Processor engine + publisher
  │   │   └── portal/            # Portal API (opt-in)
  │   └── datasets/
  │       └── usdm/resources/     # Dataset USDM, science và resources (byte-pinned)
  ├── tests/                     # Unit/component tests và integration/
  ├── warehouse/                 # Vùng warehouse/runtime
  ├── compose.yaml
  ├── Dockerfile                 # API
  ├── Dockerfile.worker          # Worker
  └── pyproject.toml             # Package và cấu hình công cụ Python
  ```

- Chi tiết ánh xạ module: `docs/AGENT_MODULES.md`.
- Giữ route/lifecycle ở `app.py`, validation/stream ở `modules/ingestion/`, registry ở
  `modules/catalog/`, object storage ở `modules/storage/`, auth ở `modules/auth/` và phân quyền ở
  `modules/authorization/`, recovery ở `modules/catalog/*maintenance.py`, processor/publish ở
  `modules/processing/`, Portal API ở `modules/portal/`.
- **Chưa thêm** Kafka/Airflow/DuckDB hoặc broker chỉ để khớp tên dự án.

## Frontend — đã migrate, ngoài phạm vi repo này

- Portal UI (React/TypeScript) **đã migrate sang repository khác**. Mọi thay đổi giao diện Portal
  thực hiện ở repo frontend tương ứng, không ở repo Server này.
- Thư mục `frontend/` (nếu còn trong cây làm việc) là bản cũ: **không** chỉnh sửa, build, test,
  format hay cập nhật nó trong repo này; coi như ngoài phạm vi và không dùng làm bằng chứng.
- Backend giữ nguyên HTTP/session contract tại `docs/STAGE4_API_CONTRACT.md`; đó là nguồn chuẩn
  để phía frontend tích hợp.

## File và thư mục tạm

- **Mọi file/thư mục tạm bắt buộc đặt trong `.agents/temp/`.** Không tạo file/thư mục tạm rải rác
  ở root, `scripts/`, `src/`, `tests/`, `data_lake/`, `metadata/`, `warehouse/` hay bất kỳ đâu khác
  trong repo.
- Tạo sẵn thư mục nếu chưa có trước khi ghi file tạm; dùng đường dẫn con rõ ràng bên trong
  `.agents/temp/` (ví dụ `.agents/temp/scratch/`, `.agents/temp/run-<mục-đích>/`).
- Dọn file tạm sau khi xong việc khi có thể; `.agents/temp/` được ignore trong `.gitignore` nên
  không commit file tạm mới (file đã track trước đó giữ nguyên).

## Docker images MinIO

- Các service MinIO trong Docker/Compose luôn dùng đúng hai image do người dùng tự build từ source
  MinIO: `noname12346767/my-minio` cho MinIO server và `noname12346767/mc-allos` cho MinIO Client
  (`mc`).
- Không thay chúng bằng image MinIO upstream hoặc repository khác (ví dụ `quay.io/minio/minio`,
  `quay.io/minio/mc`, `minio/minio` hay `minio/mc`). Nếu cần tag hoặc digest, vẫn phải pin trên đúng
  hai repository đã chỉ định.

## Convention code

- Python 3.11; đặt tên snake_case / PascalCase / UPPER_SNAKE_CASE như hiện có.
- Ruff chạy từ config trong `pyproject.toml`: line length 100, rules `E4,E7,E9,F`; shell init giữ LF.
- Byte-pinned scientific resources (`src/climate_platform/datasets/usdm/resources/`,
  `datasets/usdm/science.py`) **không** format/lint-fix; không sửa raw, source nguồn hay historical
  hashes.
- Dependency pin trực tiếp trong `pyproject.toml`/`requirements*.txt`; không coi venv có sẵn là
  bằng chứng clean install. Mỗi đường cài phải được chốt khi thêm dependency.

## Compatibility phải giữ

- Path/header/multipart cũ, `dataset_key` optional/fallback, HTTP 200 `VERIFIED`/`DUPLICATE`,
  `metadata.status`, UUID/`file_id`, observation identity và revision chain.
- Không đổi ownership lịch sử, hash semantics, object-key layout hoặc schema âm thầm. Thay đổi cần
  migration/backup/tests và cập nhật cả contract Client/Server.

## Dữ liệu và storage

- Không trả `VERIFIED` trước storage verify và DB commit; không fallback local tự động khi S3 lỗi.
- Không coi ETag/user metadata là checksum; raw immutable, retry idempotent; không dùng
  filename/dataset_key làm đường dẫn tùy ý.
- SQLite: connection riêng mỗi operation, transaction/unique constraints, không chia sẻ connection
  giữa threads; không đặt active DB lên object storage/network filesystem; giữ commit ngắn và
  optimistic re-check (không đưa S3 I/O trở lại writer transaction, không bỏ unique constraints).
- Giữ `.env`, runtime, raw, SQLite, pending Client, volumes và thay đổi local của người dùng.
- **Không `docker compose down -v`.** Backup SQLite bằng backup API hoặc pause writers (không chỉ
  copy DB bỏ WAL). Backup S3 theo `docs/MINIO_OPERATIONS.md`, gồm versions cần giữ. Migration/import/
  reconcile trên dữ liệu thật là thao tác riêng có backup, target rõ và kế hoạch restore.

## Git

- **Không bao giờ chạy `git stash`** trong repo này (gồm `git stash push/save/pop/apply/drop/clear`
  hay mọi biến thể). Không cất thay đổi local của người dùng vào stash.
- Không `git checkout -- <file>`, `git restore`, `git reset --hard` hay lệnh nào xóa/ghi đè thay đổi
  chưa commit của người dùng.
- Khi cần tách thay đổi, chỉ thao tác đúng phạm vi file bằng công cụ đọc/sửa file và `git diff`
  (read-only); commit chỉ khi người dùng yêu cầu rõ ràng.

## Bảo mật và cấu hình

- Map lỗi có nghĩa sang HTTP phù hợp; log stdout/audit không chứa secret.
- Không log API keys, credentials S3, payload hoặc exception chứa credential; không commit secret.
- Bảo toàn fail-closed khi accounting/auth/storage không xác minh được; readiness không sửa/chữa DB
  bằng cách tạo lại.
- Config lấy từ Settings/`.env`/OS env; kiểm tra biến có được truyền qua Compose `environment`
  không (`.env` Compose không tự chuyển mọi biến vào container).
- Giữ loopback binding, TLS ở edge, key rotation cùng identity; không tự bật legacy/static
  credentials hoặc làm public bucket để "fix kết nối".

## Testing

- Unit/component dùng `tmp_path`, key giả; fake S3 cho logic riêng, real S3 chỉ project/bucket test
  cô lập.
- Thay storage/schema/auth phải test duplicate/revision/ownership, commit failure/orphan, mất
  dependency và restart. Contract changes chạy cả Client và HTTP integration.
- Không sửa assertion để che regression; không nâng PARTIAL lên DONE chỉ vì test mock PASS.

## Bằng chứng và báo cáo

- Báo riêng kiểm tra **đã chạy**, **không chạy** và lý do môi trường; historical PASS không thay
  current evidence.
- Khi cập nhật plan: ghi command/date/test count, phần mock vs real, artifact/report path, blocker
  và người thực hiện vào file stage tương ứng trong `.agents/plans/`.

## Lệnh kiểm tra (từ root Server, dev env đã sẵn sàng)

```powershell
.\.venv\Scripts\python.exe -m ruff check --no-cache .
.\.venv\Scripts\python.exe -m ruff format --check --no-cache .
.\.venv\Scripts\python.exe -m pytest -q
# Chỉ suite HTTP thật; không cần MinIO:
.\.venv\Scripts\python.exe scripts/smoke/cross_repo_smoke.py
```

Full pytest cần sibling Client hoặc `CLIENT_REPO_PATH`; collection báo lỗi nếu thiếu.
`scripts/smoke/compose_smoke.py` cần Docker Compose >=2.24.4, artifacts/digests hợp lệ và Client; tạo
project/key/bucket/ports riêng. `scripts/smoke/s3_assertions.py` có fault injection (ghi bytes sai cố ý),
chỉ chạy trong isolated smoke project. `scripts/release/verify_images.py` có pull và tạo security-artifacts, không
phải kiểm tra offline thuần.

## Nguồn chuẩn liên quan

- Module/refactor package: `docs/AGENT_MODULES.md`
- Vận hành S3: `docs/MINIO_OPERATIONS.md`
- Tiến độ Client: `../climate-collector/AGENT.md`
- Tổng quan workspace: `../README.md`
