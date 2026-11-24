# REFACTOR — Tái cấu trúc Server theo kiến trúc module kiểu NestJS

Cập nhật: 2026-11-24 (Asia/Saigon). File này là **đề xuất plan**, chưa được giao triển khai.
Chỉ thực hiện khi người dùng giao task; roadmap không tự cấp quyền.

> **Bổ sung 2026-11-24 (đã thực hiện):** mục **12** đã chuẩn hoá tầng dữ liệu bằng **SQLAlchemy** và
> tách `entity/` · `repositories/` · `s3/` ra **cấp package** `src/climate_platform/`. Dependency
> (`SQLAlchemy==2.0.36`, `alembic==1.14.0`) đã thêm vào `requirements.txt`/`pyproject.toml`; code đã
> chuyển và test PASS (bằng chứng ở mục 12.11).

> Phần refactor cấu trúc (mục 0–10) **không** đổi hành vi. Yêu cầu "tự động đẩy Bronze → Gold khi
> đủ điều kiện" là **tính năng mới**, tách riêng ở **mục 11** — không thuộc phạm vi refactor và
> cần task/quyết định riêng trước khi triển khai.

Nguồn rules/convention: [../../AGENTS.md](../../AGENTS.md). Plan/stage hiện tại:
[AGENT.md](AGENT.md). Ánh xạ module hiện hành: [../../docs/AGENT_MODULES.md](../../docs/AGENT_MODULES.md).

---

## 0. Mục tiêu và phạm vi

### 0.1 Mục tiêu

Chuyển codebase Python/FastAPI hiện tại (đang chia theo *layer* ở một số chỗ, và một router
Portal 860 dòng) sang **kiến trúc hướng module (feature modules)** giống NestJS, để dễ quản lý:

- Mỗi bounded context là một **Module** đóng gói `controller` (route) · `service` (nghiệp vụ) ·
  `repository` (truy cập dữ liệu) · `dto` (cấu trúc dữ liệu) · `guards`/`pipes`/`middleware`.
- Tách bạch rõ: **Controller không chứa business logic**, **Service không chứa logic HTTP**,
  **Repository không chứa business logic**, **DTO không chứa logic nghiệp vụ**.
- Chuẩn hoá các thành phần xử lý request (Guard/Pipe/Interceptor/Exception Filter) thành các
  vị trí nhất quán thay vì rải rác.

### 0.2 Không thuộc phạm vi (non-goals)

- **Không viết lại sang TypeScript/NestJS thật.** Repo là Python 3.11; `AGENTS.md` cấm thêm
  framework/dịch vụ chỉ để khớp tên dự án. Plan này **áp dụng cách phân tầng của NestJS lên
  Python/FastAPI**, không đổi runtime, không đổi ngôn ngữ.
- **Không thêm DI framework** (dependency-injector, injector, punq...). Repo đã có quy ước
  "no import-time magic or third-party DI framework" (`processing/engine.py`). Dùng DI gốc của
  FastAPI (`Depends`) + một `container` wiring tường minh theo module.
- Không đổi hành vi HTTP, schema, hash/lineage, revision, ownership, object-key layout.
- Không chạm vào file byte-pinned (`datasets/usdm/resources/`, `datasets/usdm/science.py`).
- Không thêm GitHub Actions/CI/CD; mọi bằng chứng chạy local.
- **Không** thêm tính năng nghiệp vụ mới (ví dụ tự động promote Bronze → Gold). Yêu cầu đó nằm ở
  **mục 11** dưới dạng đề xuất riêng; refactor tuyệt đối không trộn nó vào các phase 0–10.

---

## 1. Quyết định cần xác nhận trước khi làm

| # | Quyết định | Đề xuất mặc định |
|---|---|---|
| D1 | NestJS-style layering trong Python (không rewrite TS) | **Có** (bắt buộc, xem 0.2) |
| D2 | Giữ `config.py` ở package root (ConfigModule) thay vì dời vào `common/` | **Giữ nguyên** — giảm churn cho 13+ import nội bộ và scripts |
| D3 | Giữ `datasets/usdm/` nguyên vị trí, coi là dataset **plugin** sau `processing` | **Giữ nguyên** — byte-pinned + `WORKER` gọi qua `Path(__file__)` |
| D4 | Có cần tầng `infrastructure/` toàn cục không? | **Bỏ** — `infrastructure/` không phải khái niệm NestJS; phân bổ về module (`storage`, `system`) |
| D5 | Composition root đặt tên `climate_platform/app.py` hay `main.py`? | **`app.py`** (AppModule + `app` cho uvicorn); `cli.py serve()` trỏ vào đây |
| D6 | Có để lại shim `climate_platform.api.*` tạm thời không? | **Không** — cập nhật atomically mọi import (theo Phase 1 "không còn shim") |
| D7 | Portal: tách 1 router lớn thành nhiều controller nhỏ? | **Có** — chia theo nhóm route (catalog / selection / admin / session); auth tách hẳn sang `modules/auth` (D8) |
| D8 | Tách `auth` + `session` khỏi `portal` thành module riêng? | **Có** — `modules/auth/` chỉ làm **authentication + session**; portal không sở hữu login/session |
| D9 | Authorization = guard riêng, tái dùng, gắn theo route như NestJS `@UseGuards`? | **Có** — `modules/authorization/guards/` export guard; module khác inject qua `Depends(...)`; **không** nhét vào middleware |
| D10 | Giữ `blob_repository.py` (pass-through) trong catalog? | **Bỏ** — `CatalogService` nhận thẳng `ObjectRepository` của `modules/storage`; giảm 1 lớp trung gian |

> Điểm **D6** rất quan trọng: refactor sẽ phải sửa đồng thời cả `src/`, `tests/`, `scripts/`,
> `Dockerfile`, `compose.yaml`, `docs/API_CONTRACT.md`. Không để trạng thái nửa vời.

> Quyết định **D11–D15** của tính năng auto-promote (mục 11) nằm **riêng ở mục 11.9** — không trộn
> vào bảng D1–D10 của refactor.

---

## 2. Nguyên tắc bất biến (compatibility — không được vi phạm)

Trích `AGENTS.md` mục "Compatibility phải giữ"; refactor **không** được đổi:

- Path/header/multipart, `dataset_key` optional/fallback.
- HTTP `200` + status `VERIFIED`/`DUPLICATE`, `metadata.status`, UUID/`file_id`,
  observation identity, revision chain.
- Ownership lịch sử, hash semantics, object-key layout, schema (không đổi âm thầm).
- Không trả `VERIFIED` trước storage verify + DB commit; không fallback local khi S3 lỗi.
- Fail-closed khi accounting/auth/storage không xác minh được; readiness không tự tạo lại DB.
- SQLite: connection riêng mỗi operation, transaction/unique constraints giữ nguyên.
- Byte-pinned: **không** format/lint-fix `datasets/usdm/resources/` và `datasets/usdm/science.py`.
- Giữ `.env`, runtime, raw, SQLite, pending Client, volumes và thay đổi local của người dùng.

**Bằng chứng bắt buộc cho mỗi phase:** `ruff check` + `ruff format --check` + `pytest -q` PASS,
và diff `openapi.json` trước/sau không đổi (trừ thay đổi có chủ ý + cập nhật contract).

> Tính năng auto-promote (mục 11) giữ **cùng** tập bất biến này; xem thêm ràng buộc riêng ở 11.6.

---

## 3. Ánh xạ khái niệm NestJS → Python/FastAPI

| NestJS | Tương đương trong repo này | Ghi chú |
|---|---|---|
| Module | package `modules/<feature>/` + `module.py` (wiring providers, export router) | Python không cho dấu `.` trong tên file → dùng `module.py`, `controller.py`, `service.py`... bên trong package |
| Controller | `controller.py` chứa `APIRouter`, handler mỏng | Không business logic, không truy vấn SQL trực tiếp |
| Service | `service.py` (`@Injectable`-tương đương = class nhận dependency qua `__init__`) | Chứa business logic; không biết HTTP |
| Repository | `repositories/` | Chỉ truy cập dữ liệu. Tách theo **công nghệ**: tên file phải nói rõ đâu là SQLite, đâu là object storage |
| Repository — relational | `modules/catalog/repositories/sqlite_repository.py` (SQLite registry) | Hiện thân phần SQL của `MetadataManager` (observations/content_blobs, revision chain) |
| Repository — object storage | `modules/storage/repositories/` (`object_repository.py` = hợp đồng; `minio_repository.py` = MinIO/S3; `local_repository.py` = filesystem Bronze) | Hiện thân `infrastructure/object_store.py`. Catalog **không** có wrapper riêng — `CatalogService` nhận `ObjectRepository` (D10) |
| DTO | `dto.py` (Pydantic `BaseModel`, `model_config=ConfigDict(extra="forbid")`) | Request/response schema; không logic nghiệp vụ |
| Entity/Model | giữ ở repository (`FileMetadata`) | Khác DTO; map DB row ↔ object |
| Middleware | `common/middleware.py` / `modules/portal/middleware.py` (Starlette ASGI/middleware) | Chạy trước route |
| Guard | `modules/authorization/guards/` (phân quyền) + `modules/auth/guards.py` (xác thực) — FastAPI `Depends` | Tương đương `@UseGuards`: export từ `module.py`, inject theo route. Authentication ở `auth`; authorization (role/grants/source) ở `authorization` (D8, D9) |
| Pipe | `validation.py` + Pydantic validators | Validate/transform input (source, source_date, filename, filter) |
| Interceptor | middleware/dependency bọc handler (request-id, security headers, timing, audit) | FastAPI không có interceptor native → dùng middleware + dependency |
| Exception Filter | `@app.exception_handler` trong `common/errors.py` / `modules/portal/errors.py` | Chuẩn hoá response lỗi |
| Providers / DI container | `module.py` của từng module + `app.py` (AppModule) + `Depends` | Wiring tường minh theo module; **không** file container toàn cục, không magic |
| AppModule / main | `climate_platform/app.py` (build_app) + `cli.py serve()` (bootstrap) | uvicorn target mới |

> Tính năng auto-promote (mục 11) **không** thêm khái niệm NestJS mới: `promoter.py` là một
> service trong `modules/processing/`, dùng lại `Depends`/`module.py`; gate đọc dữ liệu qua
> service/repository sẵn có (không truy vấn SQL trực tiếp).

---

## 4. Cấu trúc thư mục đích

> Cây dưới đây là cấu trúc đích **sau refactor 0–10 _và_ mục 12**: `entity/` · `repositories/` ·
> `s3/` được **nâng ra cấp package** `src/climate_platform/`; `modules/storage/` và mọi
> `modules/*/repositories/` bị **gỡ bỏ**. Chi tiết tầng dữ liệu ở **mục 12**.

```text
src/climate_platform/
├── __init__.py
├── app.py                     # AppModule: build_app() gom router toàn bộ module + middleware + exception filter (uvicorn target)
├── config.py                  # ConfigModule: nguồn cấu hình duy nhất (Settings/.env) + PROMOTE_* (mục 11). GIỮ NGUYÊN vị trí (D2)
├── cli.py                     # Bootstrap CLI: serve() chạy app; entry point worker/replay + `promote` (mục 11)
│
├── common/                    # CROSS-CUTTING dùng chung mọi module — KHÔNG chứa business logic
│   ├── __init__.py
│   ├── errors.py              #   Exception Filter: lỗi domain → HTTP, chuẩn hoá response lỗi
│   ├── middleware.py          #   Middleware: auth SỚM (trước multipart) + rate limit + accounting + audit
│   │                          #   (SQL access.sqlite3 → repositories/access_repository.py — mục 12)
│   ├── pipes.py               #   Pipe/validator tái sử dụng (source, date, cursor/limit...)
│   └── interceptors.py        #   Interceptor-helper: request-id, security headers, timing
│
├── entity/                    # [MỚI — mục 12] SQLAlchemy ORM entity (map bảng ↔ object). Cấp package.
│   ├── __init__.py
│   ├── base.py                #   DeclarativeBase + naming_convention + type map (giữ CHECK/UNIQUE/FK)
│   ├── registry.py            #   ingestion.sqlite3: Observation, ContentBlob, RecoveryReport
│   ├── control.py             #   control.sqlite3: User, Session, Grant, Transient, Audit, Config, PortalUsage, Lease
│   ├── warehouse.py           #   warehouse.sqlite3: Build, Attempt, GoldCell (+ view gold_weekly)
│   └── access.py              #   access.sqlite3: AccessUsage
│
├── repositories/              # [MỚI — mục 12] Tầng truy cập dữ liệu SQL (SQLAlchemy). Cấp package.
│   ├── __init__.py
│   ├── database.py            #   Engine factory: NullPool + pragma WAL/synchronous/foreign_keys/busy_timeout;
│   │                          #   engine read-only (mode=ro); event "begin" → BEGIN IMMEDIATE; map BUSY→503
│   ├── catalog_repository.py  #   observations/content_blobs/revision chain (thay modules/catalog/repositories/sqlite_repository.py)
│   ├── auth_repository.py     #   users + sessions (gộp user_repository + session_repository)
│   ├── authorization_repository.py  # grants
│   ├── control_repository.py  #   transient/usage/leases/audit/config (+ facade Store)
│   ├── access_repository.py   #   rate-limit/quota accounting (access.sqlite3)
│   ├── warehouse_repository.py#   builds/attempts/gold_cells (warehouse.sqlite3)
│   └── releases.py            #   snapshot/backup read-only của release (thay portal/repositories/releases.py)
│
├── s3/                        # [MỚI — mục 12] Object storage repository (MinIO/S3 + local Bronze). Cấp package.
│   ├── __init__.py
│   ├── object_repository.py   #   Hợp đồng (Protocol) ObjectRepository (publish/verify/get/list)
│   ├── minio_repository.py    #   Impl MinIO/S3 (gộp S3Storage/boto3)
│   ├── local_repository.py    #   Impl filesystem Bronze (STORAGE_BACKEND=local)
│   ├── keys.py                #   object_key builder (layout bất biến)
│   └── module.py              #   Wiring: object_repository() chọn impl theo STORAGE_BACKEND
│
# Guard KHÔNG ở common: xác thực → modules/auth/guards.py; phân quyền → modules/authorization/guards (D8/D9).
# Repository (SQL/object) KHÔNG nằm trong modules: đặt ở entity/ + repositories/ + s3/ (mục 12).
├── modules/                   # Các FEATURE MODULE — mỗi thư mục là một bounded context tự đóng gói
│   ├── __init__.py
│   ├── system/                # Module System: sức khoẻ dịch vụ — route /livez /readyz /health + probe phụ thuộc
│   │   ├── __init__.py
│   │   ├── module.py          #   Wiring: cung cấp readiness provider cho app
│   │   ├── controller.py      #   Route /livez, /readyz, /health
│   │   └── readiness.py       #   Probe SQLite/MinIO/access (đọc qua repositories/ + s3/)
│   ├── auth/                  # Module Auth: AUTHENTICATION + SESSION (tách khỏi portal — D8). Chỉ trả lời "BẠN LÀ AI"
│   │   ├── __init__.py        #   (repository users/sessions → repositories/auth_repository.py — mục 12)
│   │   ├── module.py          #   Wiring: AuthService + guard xác thực + router
│   │   ├── controllers/
│   │   │   ├── __init__.py
│   │   │   ├── login.py       #     POST /auth/login (username/password), GET /auth/info, POST /auth/logout
│   │   │   └── session.py     #     GET /session
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── password.py    #     verify username/password PBKDF2 (từ api/portal/auth.py)
│   │   │   ├── session.py     #     tạo/huỷ/đọc session
│   │   │   └── api_key.py     #     xác thực API key collector (từ api/access.authenticate)
│   │   ├── dto.py             #   DTO: UserInput, SessionOut
│   │   └── guards.py          #   Guard XÁC THỰC: require_session, require_api_key (D9)
│   ├── authorization/         # Module Authorization: PHÂN QUYỀN — trả lời "BẠN ĐƯỢC LÀM GÌ". Guard tái dùng (D9)
│   │   ├── __init__.py        #   (repository grants → repositories/authorization_repository.py — mục 12)
│   │   ├── module.py          #   Wiring: export guard cho module khác inject qua Depends
│   │   ├── guards/
│   │   │   ├── __init__.py
│   │   │   ├── require_role.py     #   Guard: role admin/user
│   │   │   ├── require_grant.py    #   Guard: quyền theo dataset
│   │   │   └── require_source.py   #   Guard: allowed sources (upload) — từ api/security.authorize_upload
│   │   └── services/
│   │       ├── __init__.py
│   │       └── policy.py      #   role + grants + allowed_sources() (từ api/portal/api.py + api/security.py)
│   ├── ingestion/             # Module Ingestion: nhận file từ collector → Bronze, dedup, ghi registry
│   │   ├── __init__.py
│   │   ├── module.py          #   Wiring: ghép controller + service + guard
│   │   ├── controller.py      #   Route /upload, /uploads (mỏng, từ api/app.py)
│   │   ├── service.py         #   Nghiệp vụ ingest: stream, SHA-256, size cap, đặt atomic (từ ingestion/service.py)
│   │   ├── dto.py             #   DTO vào/ra: IngestionResponse
│   │   └── validation.py      #   Pipe: validate source/source_date/filename (từ ingestion/validation.py)
│   ├── catalog/               # Module Catalog: registry metadata + bảo trì/reconcile
│   │   ├── __init__.py
│   │   ├── module.py          #   Wiring: service + nhận ObjectRepository từ s3/
│   │   ├── service.py         #   Orchestration registry ↔ object storage (optimistic publish)
│   │   ├── maintenance.py     #   Migrate/reconcile local (từ catalog/maintenance.py)
│   │   └── s3_maintenance.py  #   Migrate/reconcile S3 (từ catalog/s3_maintenance.py)
│   │                          #   (entity FileMetadata → entity/registry.py; repository SQL → repositories/catalog_repository.py — mục 12)
│   ├── processing/            # Module Processing: chạy processor dataset theo batch (Strategy/Registry)
│   │   ├── __init__.py
│   │   ├── module.py          #   Wiring: đăng ký processor (default_registry)
│   │   ├── contracts.py       #   Interface DatasetProcessor + ProcessorConfig/Report
│   │   ├── engine.py          #   Engine tra cứu & chạy processor
│   │   ├── publisher.py       #   Publish sản phẩm bất biến, kiểm checksum
│   │   └── promoter.py        #   [TÍNH NĂNG MỚI mục 11] Vòng lặp --watch/--once đánh giá gate
│   │                          #   Bronze→Gold rồi gọi run_pipeline; KHÔNG chứa logic dataset
│   └── portal/                # Module Portal: API xem/tải 3 tầng — opt-in (auth/session ở modules/auth, phân quyền ở modules/authorization)
│       ├── __init__.py
│       ├── module.py          #   PortalModule = install_portal() (từ api/portal/app.py); gắn middleware portal + include router portal
│       ├── config.py          #   PortalConfig
│       ├── controllers/       #   Tầng nhận request, chia theo nhóm route
│       │   ├── __init__.py
│       │   ├── catalog.py     #     sources/datasets/overview/weeks/versions/attempts
│       │   ├── selection.py   #     selections + layers/{preview,schema,quality,lineage,map} + download
│       │   └── admin.py       #     datasets/audit (users/grants chuyển sang modules/auth + modules/authorization)
│       ├── services/          #   Business logic portal
│       │   ├── __init__.py
│       │   ├── pagination.py  #     phân trang + cursor signature
│       │   ├── release.py     #     Release facade + resolve release/data
│       │   └── selection.py   #     selected()/table()/artifact_list()
│       ├── dto.py             #   DTO: SelectionInput (GrantInput → authorization, UserInput → auth)
│       ├── middleware.py      #   Middleware portal_access (CSRF, headers, audit) — KHÔNG chứa phân quyền (đã thành guard)
│       ├── errors.py          #   PortalError + exception filter
│       └── workers/           #   Tiến trình con tách biệt
│           ├── __init__.py
│           ├── reader.py      #     Gọi subprocess đọc bounded
│           ├── read_worker.py #     Subprocess reader JSON/SQLite
│           ├── prepare_gis.py #     Offline GIS index (không chạy trong request)
│           └── demo.py        #     Demo IdP loopback
│       #   (store.py control → repositories/control_repository.py; releases.py → repositories/releases.py — mục 12)
│
└── datasets/usdm/             # Plugin dataset USDM (byte-pinned + subprocess path — GIỮ NGUYÊN, D3)
    ├── processor.py           #   Orchestrate replay USDM Bronze→Silver→Gold
    ├── science.py             #   GIS worker (byte-pinned, KHÔNG sửa)
    └── resources/...          #   Resource byte-pinned (KHÔNG format/lint)
```

### 4.1 Quy ước mỗi module

Mỗi `modules/<feature>/module.py` là nơi **duy nhất** wiring:

```python
# modules/ingestion/module.py
from fastapi import APIRouter
from .controller import router as controller_router
from .service import IngestionService
from climate_platform.modules.catalog.service import CatalogService

def ingestion_router(catalog: CatalogService) -> APIRouter:
    # provider tường minh, không magic; service nhận dependency qua tham số
    service = IngestionService(catalog=catalog)
    return controller_router(service)
```

`app.py` (AppModule) chỉ: tạo `FastAPI`, gọi `settings.ensure_directories()`, chạy lifespan,
`include_router` từ các module, add middleware, đăng ký exception handlers.

**Định nghĩa Done cho một module:**
- Có đủ `module.py`, `controller.py` (mỏng), `service.py` (nghiệp vụ), `repositories/` (nếu truy
  cập dữ liệu), `dto.py` (nếu có input/output).
- Controller không import `sqlite3`/`boto3`; service không import `Request`/`Response`/`HTTPException`
  (lỗi domain map ở filter).
- Test của module PASS; route/response không đổi so với baseline.

> **Cập nhật bởi mục 12 (D21):** repository **không** còn nằm trong `modules/*/repositories/`. Tầng
> dữ liệu được nâng ra **cấp package**: `entity/` (SQLAlchemy entity), `repositories/` (SQL, đặt tên
> theo **domain**: `catalog_repository.py`, `auth_repository.py`…), `s3/` (object storage). Quy ước
> "đặt tên theo công nghệ" bên dưới chỉ còn áp dụng cho các impl trong `s3/`.

**Quy ước đặt tên (bắt buộc — "mỗi thứ làm một việc", đọc tên là hiểu):**
- **Repository đặt tên theo công nghệ**, không theo nghiệp vụ mơ hồ: `sqlite_repository.py` (SQLite)
  vs `minio_repository.py` / `local_repository.py` (object storage/filesystem). Cấm tên kiểu
  `observation_repository.py`/`blob_repository.py` cho hai công nghệ khác nhau.
- **Guard là đơn vị riêng, tái dùng**: đặt ở `modules/authorization/guards/` (phân quyền) và
  `modules/auth/guards.py` (xác thực); export từ `module.py`, inject qua `Depends(...)`
  (tương đương `@UseGuards`) — không nhét vào middleware, không viết lại logic ở mỗi route.
- **Mỗi module một trách nhiệm**: authentication (`auth`), phân quyền (`authorization`), registry
  (`catalog`), object storage (`storage`)… Không gộp nhiều vai trò vào một module.

### 4.2 Tầng repository cho MinIO/S3 (object storage)

> **Cập nhật bởi mục 12:** tầng này được nâng từ `modules/storage/` lên **cấp package `s3/`**
> (`s3/object_repository.py`, `s3/minio_repository.py`, `s3/local_repository.py`, `s3/keys.py`,
> `s3/module.py`). Các đường dẫn `modules/storage/*` dưới đây giữ nguyên ý nghĩa, chỉ đổi vị trí sang `s3/`.

Trong repo hiện tại, truy cập MinIO/S3 nằm trực tiếp trong `infrastructure/object_store.py`
(`S3Storage` + `object_key`) và bị gọi lẫn trong `catalog/repository.py::_register_s3`. Đây là
điểm chưa đúng kiểu NestJS: **repository là tầng truy cập dữ liệu duy nhất**, không phân biệt
SQLite hay object storage. Plan gom vào module `storage`, **không giữ tầng driver riêng**:

- `modules/storage/repositories/object_repository.py`: định nghĩa `Protocol`/interface
  `ObjectRepository` với các thao tác domain: `publish(local_path, key, sha256, size)`,
  `verify(key, sha256, size, bucket)`, `get_object(...)`, `objects()` (list).
- `modules/storage/repositories/minio_repository.py`: **cài đặt MinIO/S3** — sở hữu luôn boto3 client
  (gộp `S3Storage` từ `object_store.py` vào repository; không còn file driver riêng vì repository
  chính là nơi duy nhất nói chuyện với MinIO).
- `modules/storage/repositories/local_repository.py`: cài đặt filesystem Bronze cho
  `STORAGE_BACKEND=local` (tách khỏi nhánh `if settings.STORAGE_BACKEND == "s3"` hiện nằm trong
  `MetadataManager.register_upload`).
- `modules/storage/module.py`: chọn implementation theo `settings.STORAGE_BACKEND` và export
  provider `object_repository()` (tường minh, không magic).
- `modules/storage/keys.py`: `object_key(...)` (chuyển từ `object_store.py`; **giữ nguyên layout**).

> `readiness.py` (probe SQLite/S3/access) không thuộc storage; nó là mối quan tâm của `system`,
> nên chuyển về `modules/system/readiness.py` và gọi repository qua provider thay vì import trực tiếp.

Quan hệ với `catalog`:
- `modules/catalog/repositories/sqlite_repository.py`: **chỉ SQL** (observations, content_blobs,
  revision chain, unique constraints, WAL, connection-per-op) — hiện thân phần SQL của
  `MetadataManager`. Tên file nói rõ đây là SQLite.
- Catalog **không** có repository object storage riêng (không `blob_repository.py` — D10):
  `modules/catalog/service.py` nhận thẳng `ObjectRepository` (hợp đồng của `modules/storage`) qua
  wiring. Một lớp ít hơn, không pass-through.
- `modules/catalog/service.py` (MỚI): **orchestration** phần "optimistic publication" (DB ↔ object
  storage) đang nằm trong `_register_s3`, vì đây là business logic bắc cầu hai repository.

**Bất biến khi tách tầng (bắt buộc giữ):**
- Object-key layout, hash semantics, revision chain, ownership: **không đổi**.
- Không coi ETag/user metadata là checksum; raw immutable; retry idempotent; conditional PUT
  `IfNoneMatch="*"`; orphan adoption sau PUT như hiện tại.
- **Không đưa S3 I/O vào writer transaction** — giữ đúng "optimistic publication" trong service
  (không DB connection/transaction bao quanh S3 I/O).
- Không fallback local tự động khi S3 lỗi; fail-closed.
- Dùng đúng image MinIO của người dùng (`noname12346767/my-minio`, `noname12367/my-allos` không liên
  quan code) — chỉ ảnh hưởng Compose, không đổi trong refactor.

### 4.3 Vì sao bỏ tầng `infrastructure/`

`infrastructure/` là khái niệm của **hexagonal/DDD**, không có trong NestJS. NestJS tổ chức theo
module: adapter hạ tầng nằm ngay trong module sở hữu nó dưới dạng provider/repository. Giữ một
tầng `infrastructure/` toàn cục trong repo này gây:

- **Trùng lớp:** `object_store.S3Storage` + `storage/repositories/minio_repository.py` là hai lớp cho
  cùng một việc; repository đã *là* nơi nói chuyện với MinIO nên gộp driver vào repository.
- **Phá vòng phụ thuộc rõ ràng:** `readiness.py` import ngược `api.access`/`catalog.repository` —
  đúng ra thuộc `system` và nhận dependency qua provider.
- **Khó trả lời "cái gì thuộc tầng này":** `container.py` (DI) trùng vai với `module.py` + `app.py`.

Vì vậy: `object_store` → gộp vào `modules/storage`; `readiness` → `modules/system`; `container` →
bỏ (wiring theo module). Đây thuần là quyết định cấu trúc, **không đổi hành vi**.

### 4.4 Tóm tắt từng file — tác dụng và nội dung

Quy ước: "Tác dụng" = file để làm gì (trách nhiệm); "Nội dung" = thành phần chính bên trong.

#### Root package `src/climate_platform/`

| File | Tác dụng | Nội dung |
|---|---|---|
| `__init__.py` | Đánh dấu package cài được | Rỗng / metadata |
| `app.py` | Composition root (AppModule): dựng FastAPI app duy nhất | `build_app()`; lifespan (`ensure_directories`, init registry/access, `validate_storage`); gắn `AccessMiddleware`; include router `system`/`ingestion`/`portal`; đăng ký exception filters; object `app` cho uvicorn (thay `api/app.py`) |
| `config.py` | ConfigModule: nguồn cấu hình duy nhất | `Settings` (pydantic-settings), `APIKeyRecord`, các property path (`bronze_path`, `metadata_path`, `scratch_path`, `temp_path`...), validator keys/storage; singleton `settings`; **[mục 11]** thêm `PROMOTE_ENABLED` (mặc định false), `PROMOTE_INTERVAL`, `PROMOTE_MAX_CONCURRENCY`, `PROMOTE_SOURCES` |
| `cli.py` | Bootstrap/entry CLI | `serve()` (uvicorn `climate_platform.app:app`), `usdm_replay`, `usdm_worker`, `verify_usdm`, `prepare_portal`; **[mục 11]** thêm `promote --once` / `promote --watch` (không xoá/đổi lệnh cũ) |

#### `common/` — cross-cutting dùng chung

| File | Tác dụng | Nội dung |
|---|---|---|
| `__init__.py` | Package marker | Rỗng |
| `errors.py` | Exception Filter dùng chung | Lỗi domain + handler map sang HTTP, chuẩn hoá payload `{"detail": ...}`; giữ tương thích `HTTPException` |
| `guards.py` | Guard xác thực/authorization dùng chung | `get_current_client` (header API key, cache `request.state`), `allowed_sources`, gọi `authenticate`; đọc `settings.API_KEYS`/static keys |
| `middleware.py` | Middleware cấp app | `AccessMiddleware`: auth trước multipart, `charge` rate-limit/quota (SQLite), cap body upload, audit log JSON; `access_probe` (từ `api/access.py`) |
| `pipes.py` | Pipe/validator tái sử dụng | Sanitize filename, validate source/source_date dùng chung (tách từ `ingestion/validation.py` khi cần chia sẻ) |
| `interceptors.py` | Interceptor-helper | Sinh `request_id`, set security headers (nosniff/referrer/CSP của portal), đo timing + logging |

#### `modules/system/` — sức khoẻ dịch vụ

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring system module | Cung cấp `readiness` provider + router |
| `controller.py` | Route hệ thống | `GET /livez`, `/readyz`, `/health` (503 khi readiness fail, `Cache-Control: no-store`) |
| `readiness.py` | Probe phụ thuộc | `sqlite_probe`, `s3_probe_client`, `validate_storage`, class `Readiness` (cache TTL) — từ `infrastructure/readiness.py`; nhận repository/provider thay vì import chéo |

#### `modules/auth/` — authentication + session (tách khỏi portal, D8)

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring auth module | `AuthService` + repository + guard xác thực + router; export service/guard cho module khác |
| `controllers/login.py` | Route đăng nhập | `POST /auth/login` (username/password), `GET /auth/info`, `POST /auth/logout` (từ `api/portal/auth.py`) |
| `controllers/session.py` | Phiên người dùng | `GET /session` (user, role, csrf, demo) |
| `services/password.py` | Xác thực mật khẩu | verify PBKDF2 username/password (từ `api/portal/auth.login` + `store.authenticate`) |
| `services/session.py` | Vòng đời session | tạo/huỷ/đọc session, rotate cookie |
| `services/api_key.py` | Xác thực API key | `authenticate()` (từ `api/access.py`) |
| `repositories/user_repository.py` | SQLite users/roles | users + roles (tách từ Portal `Store`) |
| `repositories/session_repository.py` | SQLite sessions | sessions |
| `repositories/api_key_repository.py` | Kho API key | đọc `settings.API_KEYS`/static keys |
| `dto.py` | DTO auth | `UserInput`, session output |
| `guards.py` | Guard **xác thực** | `require_session`, `require_api_key` (D9) — chỉ trả lời "bạn là ai" |

#### `modules/authorization/` — phân quyền, guard tái dùng (D9)

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring authorization module | export guard + `policy` provider cho module khác inject |
| `guards/require_role.py` | Guard theo role | admin/user |
| `guards/require_grant.py` | Guard theo grant | quyền theo dataset |
| `guards/require_source.py` | Guard theo source | `allowed_sources` cho upload (từ `api/security.authorize_upload`) |
| `services/policy.py` | Luật phân quyền | role + grants + `allowed()`/`admin()` (từ `api/portal/api.py` + `api/security.py`) |
| `repositories/grant_repository.py` | SQLite grants | grants (tách từ Portal `Store`) |

#### `modules/ingestion/` — nhận file → Bronze

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring ingestion module | Ghép controller + `IngestionService` + guard |
| `controller.py` | Route nhận upload | `POST /upload`, `GET /uploads` (mỏng; từ `api/app.py`) |
| `service.py` | Nghiệp vụ ingest | `IngestionService`/`process_file_upload`: stream chunk, SHA-256, size cap, temp file + fsync, gọi catalog service, cleanup temp (từ `ingestion/service.py`) |
| `dto.py` | DTO vào/ra | `IngestionResponse` (`status`, `message`, `metadata`) |
| `validation.py` | Pipe validate input | `sanitize_filename`, `validate_source`, `validate_source_date` (từ `ingestion/validation.py`) |

#### `modules/storage/` — repository cho object storage

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring storage module | `storage_provider()` chọn impl theo `settings.STORAGE_BACKEND` |
| `repositories/object_repository.py` | Định nghĩa hợp đồng repository | `Protocol ObjectRepository`: `publish`, `verify`, `get_object`, `objects`, thuộc tính `bucket` |
| `repositories/minio_repository.py` | Cài đặt MinIO/S3 | Bọc/gộp `S3Storage` + boto3 client (conditional PUT `IfNoneMatch`, orphan adoption, verify) |
| `repositories/local_repository.py` | Cài đặt filesystem Bronze | Ghi/đọc raw local khi `STORAGE_BACKEND=local` (tách khỏi nhánh trong `register_upload`) |
| `keys.py` | Sinh object key | `object_key(source, date, dataset_key, revision, sha256, filename)` — layout bất biến (từ `object_store.py`) |

#### `modules/catalog/` — registry + bảo trì

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring catalog module | Cấp `CatalogService` + `sqlite_repository`; nhận `ObjectRepository` từ `modules/storage` |
| `model.py` | Entity | `FileMetadata` (map DB row ↔ object; giữ field/status/revision) |
| `service.py` | Orchestration nghiệp vụ | "Optimistic publication" DB ↔ object storage (từ `_register_s3`): không S3 I/O trong writer transaction, retry, fail-closed. Dùng thẳng `ObjectRepository` — không wrapper |
| `repositories/sqlite_repository.py` | Truy cập SQLite | Bảng `observations`/`content_blobs`, revision chain, unique constraints, WAL, connection-per-op (phần SQL của `MetadataManager`). Tên nói rõ SQLite |
| `maintenance.py` | Migrate/reconcile local | `migrate_json`, `reconcile` (từ `catalog/maintenance.py`) |
| `s3_maintenance.py` | Migrate/reconcile S3 | `migrate_bronze`, `reconcile_s3`, `local_inventory` (từ `catalog/s3_maintenance.py`) |

#### `modules/processing/` — chạy processor dataset

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | Wiring processing module | Đăng ký processor (`default_registry`) |
| `contracts.py` | Hợp đồng strategy | `DatasetProcessor` Protocol, `ProcessorConfig`, `ProcessingReport` |
| `engine.py` | Điều phối | `run_pipeline`, `ProcessorRegistry`, `default_registry` |
| `publisher.py` | Publish sản phẩm | `file_hash`, `publish_atomic`, `product_path` (ghi-then-verify, không ghi đè payload khác) |
| `promoter.py` | **[TÍNH NĂNG MỚI mục 11]** Auto-promote Bronze→Gold | Vòng lặp `--watch`/`--once`; đánh giá gate **G1–G6** qua service/repository hiện có (không SQL trực tiếp); gọi `run_pipeline`; idempotent + fail-closed; không chứa business logic dataset |

#### `modules/portal/` — API xem/tải 3 tầng (opt-in)

| File | Tác dụng | Nội dung |
|---|---|---|
| `module.py` | PortalModule/wiring | `install_portal(app, config)`: middleware `portal_access`, exception handlers, include router, mount `assets`, route shell `/portal` (từ `api/portal/app.py`) |
| `config.py` | Cấu hình Portal | `PortalConfig` (env `PORTAL_*`), validate URL/path, `callback`, `secure_cookie` |
| `controllers/catalog.py` | Duyệt dữ liệu | `/sources`, `/datasets`, `/datasets/{did}`, `/weeks`, `/versions`, `/attempts`, `/overview` |
| `controllers/selection.py` | Chọn & xem tầng | `POST /selections`; `.../layers/{layer}/{preview,schema,quality,lineage,map}`; `.../artifacts/{aid}/download` |
| `controllers/admin.py` | Quản trị portal | `/admin/datasets`, `/admin/audit` (users/grants đã chuyển sang `modules/auth` + `modules/authorization`) |
| `services/pagination.py` | Phân trang | `paginate()`, `date_range()`, ký `signature` cursor |
| `services/release.py` | Truy cập release | `release()`/`data()` + facade `Release` |
| `services/selection.py` | Xử lý selection | `selected()`, `table()`, `artifact_list()` |
| `repositories/store.py` | SQLite control (portal-only) | `Store`: transient/usage/leases/audit/config (từ `api/portal/store.py`); users/sessions/grants tách sang `auth`/`authorization` |
| `repositories/releases.py` | Release bất biến | `Release`, `prepare_release`, `verify_release`, `activate`, `contained`, `sha256`, `dataset_id` (từ `api/portal/releases.py`) |
| `dto.py` | DTO portal | `SelectionInput` (+ response model); `GrantInput` → `authorization`, `UserInput` → `auth` |
| `middleware.py` | Middleware portal | `portal_access`: request-id, demo loopback check, CSRF, content-length cap, lease preview, security/CSP headers, audit denial |
| `errors.py` | Lỗi portal | `PortalError` + `error_response` + filter (map `RequestValidationError`→`INVALID_FILTER`) |
| `workers/reader.py` | Đọc bounded | Gọi subprocess `read_worker.py`, timeout, map exit code → `PortalError` (từ `api/portal/reader.py`) |
| `workers/read_worker.py` | Reader cô lập | Đọc JSON/SQLite trong subprocess, giới hạn memory/output (từ `api/portal/read_worker.py`) |
| `workers/prepare_gis.py` | Index GIS offline | Sinh `table.json`/`map-*.json` bằng geopandas (chỉ chạy offline) |
| `workers/demo.py` | Demo accounts loopback | `create_demo_app`, `seed_demo`, `DEMO_USERS` (chỉ dùng local/demo) |

#### `datasets/usdm/` — plugin dataset (GIỮ NGUYÊN)

| File | Tác dụng | Nội dung |
|---|---|---|
| `processor.py` | Orchestrate replay USDM | `discover`, `package_raw`, `run_pipeline`, `process_week`, `UsdmProcessor`, `exclusive_run` (Bronze→Silver→Gold + warehouse SQLite) |
| `science.py` | GIS worker | Xử lý khoa học trong interpreter riêng (byte-pinned, KHÔNG sửa) |
| `resources/...` | Resource byte-pinned | Cleaner + historical recipes (KHÔNG format/lint) |

> Ghi chú: mọi file `__init__.py` chỉ là package marker (rỗng) trừ khi cần export provider tường minh.

---

## 5. Kế hoạch theo phase

> Thứ tự được thiết kế để **luôn ở trạng thái chạy được** sau mỗi phase, ưu tiên "khóa hành vi
> trước, di chuyển sau". Mỗi phase có **exit criteria** và **bằng chứng** riêng.
> Ghi bằng chứng (command/date/test count) vào file này khi thực thi.
> Phase **0–7** dưới đây là **refactor thuần** (không đổi hành vi). Phase **P1–P4** của tính năng
> auto-promote nằm riêng ở **mục 11.7** — không trộn vào các phase refactor.

### Phase 0 — Baseline & khoá hợp đồng (không đổi code)

- Tạo `.agents/temp/refactor/` cho scratch.
- Chạy và lưu baseline: `ruff check`, `ruff format --check`, `pytest -q` (ghi số test; lưu ý full
  pytest cần sibling Client hoặc `CLIENT_REPO_PATH`).
- Snapshot OpenAPI: `GET /openapi.json` → lưu `.agents/temp/refactor/openapi.baseline.json`.
- Lập **inventory import** (đã có sẵn khi soạn plan, cập nhật nếu cần):
  - `tests/`: `api.app`, `access`, `security`, `catalog.repository`, `catalog.maintenance`,
    `catalog.s3_maintenance`, `ingestion.service`, `api.portal.*`, `datasets.usdm.processor`,
    `datasets.usdm.science`, `infrastructure.*`, `config`.
  - `scripts/`: `config`, `catalog.repository`, `catalog.maintenance`, `catalog.s3_maintenance`,
    `infrastructure.object_store`, `datasets.usdm.processor`, `api.portal.{releases,store,config,demo}`,
    `api.app`, `ingestion.service`, `api.access`.
  - Hạ tầng: `Dockerfile`, `Dockerfile.worker`, `compose.yaml`, `pyproject.toml`
    (`uvicorn climate_platform.api.app:app`).
- Liệt kê **điểm ghép path bằng `Path(__file__)`** phải cập nhật khi di chuyển:
  `api/portal/reader.py` → `read_worker.py`; `api/portal/releases.py` → `prepare_gis.py`;
  `datasets/usdm/processor.py` → `science.py` (`WORKER`); `api/portal/demo.py` → `install_portal`.

**Exit:** baseline PASS + OpenAPI snapshot + inventory đầy đủ đã ghi vào plan.
**Bằng chứng:** log command + số test + đường dẫn snapshot.

---

### Phase 1 — Khung `common/` + `app.py` (giữ nguyên hành vi)

Mục tiêu: dựng bộ khung cross-cutting và composition root **trước** khi dời feature.

- Tạo `common/errors.py`, `common/middleware.py`, `common/pipes.py`, `common/interceptors.py`
  (rỗng/khung + docstring). Guard **không** để ở `common/`: xác thực ở `modules/auth`, phân quyền ở
  `modules/authorization` (xem Phase 5).
- Tạo `climate_platform/app.py` = chuyển nội dung `api/app.py` sang (giữ nguyên route/behavior),
  trỏ import sang module mới; cập nhật uvicorn target.
- **Không** tạo file container toàn cục: wiring đặt trong `module.py` từng module + `app.py`.
- Cập nhật: `cli.py serve()`, `Dockerfile`, `compose.yaml` (nếu có CMD), test import
  (`tests/api/test_server.py`, `tests/api/test_readiness_security.py` dùng
  `import climate_platform.api.app as main`).

**Exit:** app khởi động, OpenAPI diff = 0 (không tính đổi thứ tự), toàn bộ test PASS.
**Rủi ro:** quên một chỗ tham chiếu `api.app` (grep `api.app` toàn repo trước khi chốt).

---

### Phase 2 — Module `system` và `ingestion`

- **system**: `/livez`, `/readyz`, `/health` → `modules/system/{module,controller}.py`;
  `infrastructure/readiness.py` → `modules/system/readiness.py` (probe gọi repository/service qua
  provider, không import trực tiếp `metadata_manager`/`api.access`).
- **ingestion**:
  - `ingestion/service.py` → `modules/ingestion/service.py` (đổi class/`IngestionService` bọc
    `process_file_upload`; giữ nguyên chunked streaming, SHA-256, size limit, cleanup temp).
  - `ingestion/validation.py` → `modules/ingestion/validation.py` ("pipes").
  - `IngestionResponse` → `modules/ingestion/dto.py`.
  - Handler `/upload`, `/uploads` → `modules/ingestion/controller.py` (mỏng).
  - `get_current_client` (xác thực) → `modules/auth/guards.py`; `allowed_sources`/`authorize_upload`
    (phân quyền) → `modules/authorization/guards/require_source.py` (đầy đủ ở Phase 5; phase này giữ
    nguyên vị trí, chỉ đổi import).
  - `api/access.py` (`AccessMiddleware`, `authenticate`, `charge`, `access_probe`) →
    `common/middleware.py` + phần auth dùng chung; `access_probe` phục vụ readiness nên để
    `modules/system/readiness.py` gọi qua provider ổn định (không import chéo ngược).
- Cập nhật import trong `tests/api/*`, `scripts/ops/test_upload.py`, `catalog/maintenance.py`
  (đang import `validate_source`, `validate_source_date` từ `ingestion.service`).

**Exit:** `/upload` trả đúng `VERIFIED`/`DUPLICATE`; ownership/revision/`metadata.status` không đổi;
test `test_server`, `test_stage2_registry`, `test_stage15`, `test_readiness_security` PASS.

---

### Phase 3 — Module `storage`: tầng repository cho MinIO/S3

Mục tiêu: tách truy cập object storage (MinIO/S3) và filesystem Bronze thành **tầng repository**
riêng, đúng kiểu NestJS.

- Tạo `modules/storage/keys.py`: chuyển `object_key(...)` từ `infrastructure/object_store.py`
  (giữ nguyên layout key, không đổi hash semantics).
- Tạo `modules/storage/repositories/object_repository.py`: `Protocol ObjectRepository`
  (`publish`, `verify`, `get_object`, `objects`, `bucket`).
- Tạo `modules/storage/repositories/minio_repository.py`: cài đặt MinIO/S3, **gộp `S3Storage`** và
  boto3 client từ `infrastructure/object_store.py` vào repository (không giữ file driver riêng).
  Giữ conditional PUT, orphan adoption, verify. Xoá `infrastructure/object_store.py` sau khi xong.
- Tạo `modules/storage/repositories/local_repository.py`: cài đặt filesystem Bronze, tách khỏi
  nhánh `if settings.STORAGE_BACKEND == "s3"` hiện nằm trong `MetadataManager.register_upload`.
- Tạo `modules/storage/module.py`: `storage_provider()` chọn impl theo `settings.STORAGE_BACKEND`
  (tường minh, không magic).

**Exit:** `object_key` output không đổi (test `tests/infrastructure/test_s3_keys.py` PASS);
publish/verify giữ nguyên invariant; chưa bắt buộc di chuyển logic catalog ở phase này.
**Rủi ro:** đây là "đường nóng" ghi dữ liệu — làm sau khi Phase 2 đã xanh.

---

### Phase 4 — Module `catalog` + `processing` (dùng repository storage)

- **catalog**: `repository.py`, `maintenance.py`, `s3_maintenance.py` → `modules/catalog/`.
  - Tách `FileMetadata` → `modules/catalog/model.py` (entity).
  - Tách `MetadataManager` (SQLite) → `modules/catalog/repositories/sqlite_repository.py`
    (connection-per-op, WAL, unique, revision chain — **không đổi semantics**). Tên nói rõ SQLite.
  - Không tạo `blob_repository.py`: `service.py` nhận thẳng `ObjectRepository` của `modules/storage` (D10).
  - `modules/catalog/service.py` (MỚI): orchestration "optimistic publication" (DB ↔ S3) từ
    `_register_s3`; giữ đúng "không S3 I/O trong writer transaction", retry, orphan adoption,
    fail-closed, reconcile.
  - `maintenance.py`/`s3_maintenance.py` dùng service/repository mới, giữ nguyên ngữ nghĩa
    reconcile/migrate (không xóa raw, backup trước khi ghi).
- **processing**: `contracts.py`, `engine.py`, `publisher.py` → `modules/processing/`; thêm
  `modules/processing/module.py` bọc `default_registry()`.
- `datasets/usdm/` **giữ nguyên** (D3). `processing.module` import `UsdmProcessor` như cũ.

**Exit:** registry/S3 store không đổi; `tests/api/test_stage2_registry`, `tests/backup/*`,
`tests/usdm/*` (logic, không GIS), `tests/infrastructure/test_s3_keys` PASS; S3 path dùng fake
S3 (logic) — real MinIO chỉ ở project/bucket test cô lập. GIS test vẫn opt-in qua `USDM_GIS_PYTHON`.

---

### Phase 5 — Module `auth` + `authorization` (tách khỏi portal và middleware)

Mục tiêu: authentication + session thành module riêng; phân quyền thành guard tái dùng — **trước**
khi đụng portal, để portal chỉ còn việc xem/tải dữ liệu.

- **auth** (`modules/auth/`):
  - `api/portal/auth.py` (`auth_router`: password login/info/logout) →
    `modules/auth/{services/password,services/session,controllers/login}.py`.
  - Route `GET /session` (đang nằm trong `auth_router`) → `modules/auth/controllers/session.py`.
  - `api/access.py::authenticate` → `modules/auth/services/api_key.py`; `initialize_access_store`,
    `access_probe`, `charge` (accounting) → `common/middleware.py` (hoặc `modules/auth` tùy nơi
    gọi), giữ nguyên semantics rate-limit/quota.
  - users/roles/sessions tách khỏi Portal `Store` → `modules/auth/repositories/`.
  - Guard xác thực: `require_session` (portal), `require_api_key` (collector).
- **authorization** (`modules/authorization/`):
  - `api/security.py::allowed_sources` + `authorize_upload` + phần role/grants trong
    `api/portal/api.py` → `modules/authorization/services/policy.py`.
  - Guard `require_role`, `require_grant`, `require_source` → `modules/authorization/guards/`.
  - grants tách khỏi Portal `Store` → `modules/authorization/repositories/grant_repository.py`.
  - Export guard từ `module.py`; module khác inject bằng `Depends(...)` (D9). Ví dụ:
    `@router.get("/admin/users", dependencies=[Depends(require_role("admin"))])`.

**Giữ bất biến:** auth-trước-multipart cho `/upload` vẫn do `AccessMiddleware` (`common/middleware.py`)
đảm nhiệm — **không** chuyển sang guard; guard chỉ lo phân quyền. Loopback demo check, CSRF,
content-length cap giữ nguyên ở portal middleware.

**Exit:** `/auth/login|callback|logout`, `GET /session`, `/upload` (allowed sources), endpoint
admin role/grants hoạt động y hệt; `tests/portal/test_portal.py`, `tests/api/test_server.py`,
`tests/api/test_readiness_security.py` PASS; OpenAPI diff = 0.

---

### Phase 6 — Module `portal` (thay đổi lớn nhất — tách nhỏ dần)

Thực hiện theo 4 bước nhỏ, mỗi bước chạy `tests/portal/test_portal.py`:

1. **Repositories**: `store.py` (portal-only: transient/usage/leases/audit/config), `releases.py` →
   `modules/portal/repositories/`.
   - `Release`, `Store`, `PortalError` giữ nguyên; `PortalError` chuyển sang
     `modules/portal/errors.py` và re-export nội bộ (không shim ra ngoài package).
   - users/sessions/grants đã tách ở Phase 5 — `Store` portal không còn giữ chúng.
2. **Workers**: `reader.py`, `read_worker.py`, `prepare_gis.py`, `demo.py` →
   `modules/portal/workers/`. Cập nhật path `Path(__file__).with_name(...)` và import
   `from ..module import install_portal` trong `demo.py`.
3. **Middleware + errors**: `portal_access` → `modules/portal/middleware.py` (KHÔNG chứa phân quyền);
   `error_response` + `handle_portal_error` + `validation_error` + `INVALID_FILTER` map →
   `modules/portal/errors.py`.
4. **Controllers + services**: tách `api/portal/api.py` (860 dòng) theo nhóm route:
   - `controllers/catalog.py`: `/sources`, `/datasets`, `/datasets/{did}`, `/weeks`, `/versions`,
     `/attempts`.
   - `controllers/selection.py`: `POST /selections`, `.../layers/{layer}/{preview,schema,quality,
     lineage,map}`, `.../artifacts/{aid}/download`.
   - `controllers/admin.py`: `/admin/datasets`, `/admin/audit` (users/grants đã ở Phase 5).
   - Helper dùng chung (`paginate`, `date_range`, `artifact_list`, `layer_status`, `selected`,
     `table`, `data`, `release`) → `services/`; guard gọi từ `modules/authorization`.
   - `SelectionInput` → `modules/portal/dto.py`.

**Exit:** `tests/portal/test_portal.py` PASS; `install_portal` vẫn opt-in qua `PORTAL_ENABLED`;
path `PREFIX = "/api/portal/v1"`, cookie, CSRF, headers bảo mật, CSP không đổi; OpenAPI Portal
diff = 0.

> Lưu ý bảo mật: giữ nguyên thứ tự **auth trước multipart**, loopback demo check, CSRF,
> content-length cap, lease preview/download, audit denial. Refactor chỉ di chuyển vị trí code.

---

### Phase 7 — Dọn dẹp, tài liệu, hạ tầng

- Xoá package rỗng `api/` (và `api/portal/`, `api/routes/`) sau khi đã di chuyển hết.
- Cập nhật `pyproject.toml`: package-data paths nếu cần; giữ entry points
  (`climate-platform`, `climate-usdm-worker`, `climate-usdm-replay`).
- Cập nhật `Dockerfile`, `Dockerfile.worker`, `compose.yaml` (uvicorn target `climate_platform.app:app`).
- Cập nhật **tài liệu chuẩn** (bắt buộc, vì `AGENTS.md` ghi rõ ánh xạ module):
  - `AGENTS.md`: bullet "Chi tiết ánh xạ module" và câu "Giữ route/lifecycle ở `api/app.py`...".
  - `docs/AGENT_MODULES.md`: bảng ánh xạ cũ→mới (thêm cột module-based).
  - `docs/API_CONTRACT.md`: cập nhật nếu có nhắc module path (không đổi endpoint).
- Xoá `.agents/temp/refactor/` khi xong (hoặc giữ log baseline).

**Exit:** `grep -r "climate_platform.api" src scripts tests docs` chỉ còn kết quả có chủ ý (nếu có);
ruff + pytest + smoke PASS; OpenAPI diff = 0; docs đồng bộ.

---

## 6. Chiến lược test & bằng chứng

Command local (macOS/darwin, repo dùng `.venv` tại gốc Server):

```bash
.venv/bin/python -m ruff check --no-cache .
.venv/bin/python -m ruff format --check --no-cache .
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke/cross_repo_smoke.py   # HTTP thật, không cần MinIO
```

(Windows theo `AGENTS.md`: `.\.venv\Scripts\python.exe ...`.)

- **Golden contract:** diff `openapi.json` sau mỗi phase với
  `.agents/temp/refactor/openapi.baseline.json`; không đổi ngoài thay đổi có chủ ý + cập nhật
  `docs/API_CONTRACT.md`/`docs/STAGE4_API_CONTRACT.md`.
- **Regression theo tầng:** chạy đúng nhóm test của phase đang sửa (api/usdm/backup/portal/config/
  infrastructure/release), rồi chạy full ở cuối mỗi phase.
- **Không sửa assertion để che regression.** Không nâng trạng thái chỉ vì mock PASS.
- **GIS:** chỉ chạy khi có `USDM_GIS_PYTHON` + `USDM_SOURCE_ROOT`; báo riêng mock vs real.
- **[Mục 11] Promoter:** gate G1–G6 test bằng fake repo (không S3 thật); case thiếu điều kiện →
  no-op, đủ → promote, chạy lại → idempotent, race writer → dừng, thiếu dependency → fail-closed.
- Ghi bằng chứng vào plan: command, ngày, số test, phần mock/real, artifact path, blocker.

---

## 7. Rủi ro và rollback

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Phá vỡ byte-pinned science | Cao | Không chạm `datasets/usdm/resources/`, `science.py`; giữ nguyên `datasets/usdm/` |
| Sai path subprocess (`read_worker`, `prepare_gis`, `science`) | Cao | Kiểm kê điểm `Path(__file__)`; test portal + usdm sau khi dời |
| Đổi hành vi HTTP ngầm | Cao | OpenAPI diff = 0; chạy `cross_repo_smoke.py` |
| Vòng import (common ↔ modules) | Trung bình | `common` chỉ phụ thuộc `config`; module không import `app.py`; repository không import controller/service |
| Bỏ sót call site (scripts/tests/Docker) | Trung bình | Phase 0 inventory + `grep` xác nhận mỗi phase |
| Portal phình to khi tách nhỏ | Trung bình | Tách theo 4 bước nhỏ (Phase 6), test sau mỗi bước |
| Tách auth/authorization phá "auth trước multipart" | Cao | Giữ `AccessMiddleware` cho `/upload`; guard chỉ lo phân quyền; chạy `tests/api/test_server.py` + `test_readiness_security.py` |
| Tách repository S3/MinIO làm sai đường ghi | Cao | Phase 3 làm độc lập; giữ object-key/hash/conditional-PUT; fake S3 cho logic, real chỉ ở bucket test |
| Thay đổi rộng khó review | Trung bình | Chia phase/commit theo module, `git` từng bước |

**Rollback:** làm theo phase trên nhánh riêng; mỗi phase là một commit độc lập để `git revert`
từng bước. Không `docker compose down -v`. Không sửa dữ liệu thật trong lúc refactor.

> Rủi ro riêng của tính năng auto-promote (race với ingest, promote lặp, gate sai, chạm raw) nằm ở
> **mục 11.8** — không trộn vào bảng rủi ro refactor ở trên.

---

## 8. Checklist import/điểm ghép phải cập nhật (kiểm soát bắt buộc)

- [ ] `src`: `catalog/maintenance.py` → `ingestion.validation`; `processing/engine.py` →
      `datasets.usdm.processor`; `datasets/usdm/processor.py` → `catalog`/`storage`/`processing.*`.
- [ ] `src` object storage: `catalog/repository.py::_register_s3`, `catalog/s3_maintenance.py`,
      `datasets/usdm/processor.py::materialize_raw`, `readiness.py` →
      repository/service của `modules/storage` (thay mọi `from ...infrastructure.object_store import ...`).
- [ ] `src` readiness: `infrastructure/readiness.py` → `modules/system/readiness.py` (bỏ import
      trực tiếp `api.access.access_probe` và `metadata_manager`).
- [ ] `src` auth/authorization: `api/access.authenticate` → `modules/auth/services/api_key.py`;
      `api/security.{get_current_client,allowed_sources,authorize_upload}` → `modules/auth/guards.py`
      (xác thực) + `modules/authorization/guards/` (phân quyền); `api/portal/auth.py` → `modules/auth/`;
      role/grants trong `api/portal/api.py` → `modules/authorization/services/policy.py`.
      Giữ `AccessMiddleware` cho auth-trước-multipart ở `common/middleware.py`.
- [ ] `tests`: `api.app`, `api.access`, `catalog.repository`, `catalog.maintenance`,
      `catalog.s3_maintenance`, `ingestion.service`, `api.portal.*`, `datasets.usdm.*`,
      `infrastructure.readiness`, `infrastructure.object_store.object_key`.
- [ ] `scripts`: `config`, `catalog.*`, `infrastructure.object_store`, `datasets.usdm.processor`,
      `api.portal.*`, `api.app`, `ingestion.service`, `api.access`.
- [ ] Hạ tầng: `pyproject.toml` (entry points/package-data), `Dockerfile`, `Dockerfile.worker`,
      `compose.yaml` (uvicorn target).
- [ ] Điểm `Path(__file__)`: `portal/repositories/releases.py`→`workers/prepare_gis.py`;
      `portal/workers/reader.py`→`workers/read_worker.py`; `datasets/usdm/processor.py`→`science.py`.
- [ ] Docs: `AGENTS.md`, `docs/AGENT_MODULES.md`, `docs/API_CONTRACT.md` (+ `STAGE4_API_CONTRACT.md`).

**Mục 11 (tính năng auto-promote — checklist riêng, chỉ khi được giao task):**

- [ ] `src`: thêm `modules/processing/promoter.py` (hoặc `modules/processing/scheduler.py`) chứa
      engine gate G1–G6; **không** SQL trực tiếp, gọi `catalog/service.py`, lease/attempt,
      `system/readiness.py`.
- [ ] `src`: `cli.py` thêm lệnh `promote --once` / `promote --watch`; giữ nguyên `usdm_replay`,
      `usdm_worker`, `verify_usdm`.
- [ ] `src`: `config.py` thêm `PROMOTE_ENABLED` (mặc định `false`), `PROMOTE_INTERVAL`,
      `PROMOTE_MAX_CONCURRENCY`, `PROMOTE_SOURCES`; xác minh truyền qua Compose `environment`.
- [ ] Hạ tầng: `compose.yaml` chạy `promote` trong **worker container sẵn có** (hoặc service mới
      nhưng **không** thêm image/broker); không thêm CI/CD.
- [ ] `tests`: gate thiếu điều kiện → no-op; đủ điều kiện → promote; chạy lại idempotent; race với
      writer (G2); thiếu dependency (G4) → fail-closed; mock vs real tách rõ.
- [ ] Báo cáo: bằng chứng P4 gồm backup/restore drill; không promote dữ liệu thật khi chưa chốt D11–D15.

---

## 9. Ước lượng & thứ tự ưu tiên

| Phase | Nội dung | Quy mô | Ưu tiên |
|---|---|---|---|
| 0 | Baseline + khoá hợp đồng | Nhỏ | Bắt buộc trước |
| 1 | Khung `common/` + `app.py` | Vừa | Cao |
| 2 | `system` + `ingestion` | Vừa | Cao |
| 3 | `storage` (repository MinIO/S3 + local) | Vừa | Cao |
| 4 | `catalog` + `processing` (dùng repository) | Vừa | Cao |
| 5 | `auth` + `authorization` (tách khỏi portal + middleware) | Vừa | Cao |
| 6 | `portal` (4 bước) | Lớn | Trung bình |
| 7 | Dọn dẹp + docs + hạ tầng | Vừa | Bắt buộc cuối |
| P1 | **[Mục 11]** Đặc tả gate G1–G6 + chốt D11–D15 + test mock | Nhỏ | Chờ task riêng |
| P2 | **[Mục 11]** `promoter.py` + `promote --once` | Vừa | Chờ task riêng |
| P3 | **[Mục 11]** `promote --watch` + `PROMOTE_*` + Compose worker | Vừa | Chờ task riêng |
| P4 | **[Mục 11]** Real path + backup/restore drill | Vừa | Chờ task riêng |

Khuyến nghị thực thi: **0 → 1 → 2 → 3 → 4 → 5 → 7 (một phần)**, để `portal` (Phase 6) sau cùng vì
ít giá trị quản lý nhất so với rủi ro và đang chờ UAT (Stage 4). Có thể dừng sau Phase 5 nếu cần.

**Mục 11 (P1–P4) độc lập với refactor:** có thể làm trước, song song, hoặc sau; nhưng **không**
gộp chung phase/commit với 0–7 và **chưa được giao** — cần trả lời D11–D15 trước khi bắt đầu P1.

---

## 10. Trạng thái

- Phase 0–7 (refactor thuần): **DONE** (2026-11-24, Asia/Saigon), thực hiện trên một phiên.
- Tính năng auto-promote Bronze→Gold (mục 11, P1–P4): **KHÔNG triển khai** (đúng phạm vi —
  là tính năng mới, cần chốt D11–D15 và task riêng).
- Chuẩn hoá tầng dữ liệu sang SQLAlchemy + tách `entity/` · `repositories/` · `s3/` (mục **12**):
  **DONE** (2026-11-24) — xem bằng chứng ở mục 12.11.

### Bằng chứng thực thi (2026-11-24)

- Baseline lấy trước khi sửa (`.agents/temp/refactor/`):
  `openapi.baseline.json` (5 paths), `openapi.portal.baseline.json` (30 paths).
- Sau refactor, **diff OpenAPI = 0**:
  `openapi.new.json` và `openapi.portal.new.json` khớp byte-for-byte (sort_keys) với baseline.
- `ruff check --no-cache .` → All checks passed.
- `ruff format --check --no-cache .` → 142 files already formatted.
- `pytest -q --ignore=tests/integration/test_loopback.py` (TMPDIR nằm trong `.agents/temp/refactor/tmp`):
  **114 passed, 5 skipped, 3 failed** — khớp đúng baseline (3 fail là lỗi môi trường macOS có sẵn:
  reader subprocess + `/var` symlink, không do refactor).
- Không chạy: `tests/integration/test_loopback.py` và `scripts/smoke/cross_repo_smoke.py` —
  thiếu sibling Client (`CLIENT_REPO_PATH`), đúng như ghi chú full pytest trong `AGENTS.md`.
- Không chạy: GIS thật (`USDM_GIS_PYTHON`/`USDM_SOURCE_ROOT`), MinIO/Compose smoke, image scan.

### Ghi chú triển khai (khác biệt nhỏ so với văn bản plan)

- `metadata_manager` (SQLite) và `CatalogService` (orchestration) tách riêng; `CatalogService`
  nhận `object_repository` (provider `modules/storage/module.py`) và gọi lại mỗi lần để tôn trọng
  monkeypatch `S3Storage`. `datasets/usdm/processor.py` dựng `CatalogService(MetadataManager(),
  object_repository)` **mới mỗi run** để giữ hành vi cô lập `settings` của test.
- `local_repository.py` sở hữu thao tác filesystem Bronze (place/verify/resolve); phần SQL của
  registry vẫn nằm trong `sqlite_repository.py` và commit cùng transaction như trước.
- `auth`/`authorization` sở hữu SQL users/sessions/grants; `portal.repositories.store.Store` giữ
  facade delegate để mọi call site và hành vi không đổi (SQL đã dời sang repo).
- `common/middleware.py` lazy-import `authenticate` từ `modules/auth` để tránh vòng import.
- Đã xóa package cũ (`api/`, `catalog/`, `infrastructure/`, `ingestion/`, `processing/`); không
  còn shim (D6). Cập nhật import trong `src`, `tests`, `scripts`, `Dockerfile`, `pyproject.toml`,
  và tài liệu (`AGENTS.md`, `docs/AGENT_MODULES.md`, `README.md`, `docs/STAGE4_*`, `STAGE_1_5_DEMO.md`).


---

## 11. [TÁCH RIÊNG — KHÔNG thuộc refactor] Tự động đẩy Bronze → Silver → Gold khi đủ điều kiện

> Mục này là **tính năng mới**, không phải refactor cấu trúc. Toàn bộ phần 0–10 giữ nguyên bất biến
> "không đổi hành vi". Muốn triển khai mục 11 cần **task riêng** và chốt các quyết định D11–D15.

### 11.1 Mục tiêu

Khi một lượt dữ liệu Bronze đã **đủ điều kiện** (xem 11.3), hệ thống **tự động** chạy pipeline
Bronze → Silver → Gold mà không cần người gọi `usdm_replay` thủ công, vẫn giữ:
- Idempotent (chạy lại không tạo sản phẩm trùng, không ghi đè payload khác).
- Fail-closed (lỗi verify/thiếu dependency → dừng, không promote nửa vời).
- Không đụng raw, không phá revision chain / ownership / object-key layout.

### 11.2 Trạng thái hiện tại (bằng chứng — chưa có auto-promote)

- USDM replay là **thủ công/offline** qua CLI: `usdm_replay`, `usdm_worker`, `verify_usdm`
  (`cli.py`); `datasets/usdm/processor.py::run_pipeline`.
- `STAGE_1_BASELINE.md:54`: chỉ **Bronze** có đường ghi S3 nghiệp vụ; Silver/Gold/warehouse là
  **local** (SQLite), Silver/Gold S3 chưa có.
- `STAGE_1_BASELINE.md:56`: "Thu thập upstream tự động: bốn collector Client vẫn là skeleton".
- Không tồn tại scheduler/cron/watcher trong `src/climate_platform` — xác nhận bằng grep toàn repo.
- `AGENT.md:40`: USDM local DONE, collector tự động phía Client **TODO**.

**Kết luận:** "đủ điều kiện → tự động Bronze → Gold" **chưa được đặc tả và chưa được cài đặt**;
mục 11 là nơi ghi nhận và thiết kế nó.

### 11.3 Điều kiện "đủ điều kiện" (eligibility gates — CẦN CHỐT, đề xuất mặc định)

Gate là điều kiện **bắt buộc tất cả đều đúng** trước khi promote một đơn vị công việc (đề xuất:
theo `(source, source_date)` hoặc theo tuần USDM):

| # | Gate | Nguồn kiểm chứng (đề xuất) | Mặc định |
|---|---|---|---|
| G1 | Bronze đã `VERIFIED` cho mọi file của đơn vị, không còn `PENDING`/lỗi | `catalog` (registry observations/content_blobs) | Bắt buộc |
| G2 | Không có lượt ingest đang mở cho đơn vị đó (không race với writer) | lease/attempt hiện có của portal store hoặc registry | Bắt buộc |
| G3 | Release/attempt trước (nếu có) đã `activate` hoặc bị đánh dấu thay thế | `portal/repositories/releases.py::verify_release/activate` | Bắt buộc |
| G4 | Đủ dependency upstream (ví dụ nguyên liệu NLDAS/USDM cần thiết cho tuần đó) | `datasets/usdm/processor.py::discover` | Bắt buộc |
| G5 | Checksum/lineage sản phẩm verify PASS sau khi ghi | `processing/publisher.py` (`file_hash`, `publish_atomic`) | Bắt buộc |
| G6 | Dưới ngưỡng tài nguyên (ổ đĩa/giới hạn song song) | `settings` + probe `system/readiness.py` | Bắt buộc |

Điểm cần người dùng quyết định (D11): đơn vị công việc là **theo file**, **theo `source_date`**,
hay **theo tuần**? Ảnh hưởng trực tiếp tới G1/G2/G4.

### 11.4 Cơ chế trigger (đề xuất — cần chốt, D12)

`AGENTS.md` cấm thêm **Kafka/Airflow/DuckDB hoặc broker chỉ để khớp tên**, và cấm CI/CD. Vì vậy
chỉ cân nhắc cơ chế **local, tường minh, không thêm dịch vụ mới**:

| Phương án | Mô tả | Ưu | Nhược |
|---|---|---|---|
| **A. CLI + `--watch` (đề xuất mặc định)** | Lệnh `climate-platform promote --watch` chạy vòng lặp kiểm gate theo `PROMOTE_INTERVAL`, gọi pipeline khi đủ điều kiện | Không thêm dịch vụ; dễ bật/tắt; chạy trong worker container sẵn có | Là tiến trình thường trú, cần supervisor (Compose đã có) |
| B. One-shot theo giờ | `promote --once` gọi bởi `cron`/systemd timer của **host** (không đưa cấu hình cron vào repo) | Đơn giản, dễ quan sát | Phụ thuộc host; độ trễ đến 1 chu kỳ |
| C. Hook sau ingest | Sau khi `/upload` commit `VERIFIED`, publish một "promote request" nội bộ | Gần thời gian thực | Dễ race với writer; khó giữ "auth trước multipart"/fail-closed |

Đề xuất: **A** làm mặc định, giữ **B** như chế độ `--once` (dùng chung 1 engine gate) để tránh
khoá cứng vào scheduler. **Không** dùng C mặc định vì đụng luồng ingest đang nhạy cảm.
Cơ chế này **không** thay thế replay thủ công; lệnh thủ công vẫn giữ nguyên.

### 11.5 Vị trí trong cấu trúc module (khớp refactor mục 4)

Tính năng này **tái dùng** cấu trúc module của refactor (nếu refactor đã xong) hoặc đặt cạnh code
hiện tại (nếu chưa refactor). Không đổi tên module hiện có:

- `modules/processing/promoter.py` (hoặc `scheduler.py`): vòng lặp `--watch`/`--once`, đánh giá
  gate G1–G6, gọi `run_pipeline` có sẵn. **Không** chứa business logic dataset.
- Gate đọc dữ liệu qua **repository/service hiện có** (`catalog/service.py`, `portal` lease,
  `system/readiness.py`) — không truy vấn SQL trực tiếp trong promoter.
- Entry point CLI mới: `climate-platform promote [--once|--watch]` trong `cli.py` (thêm cạnh
  `usdm_replay`; không xoá/đổi lệnh cũ).
- Cấu hình qua `Settings`/`.env`: `PROMOTE_ENABLED` (mặc định **false**), `PROMOTE_INTERVAL`,
  `PROMOTE_MAX_CONCURRENCY`, `PROMOTE_SOURCES` (allow-list). Kiểm tra biến có được truyền qua
  Compose `environment` (theo `AGENTS.md`).
- Đăng ký một service mới trong `compose.yaml` (worker) **chỉ khi** người dùng giao task — không
  thêm image/broker. Hoặc dùng lại worker container sẵn có với một command khác.

### 11.6 Bất biến phải giữ (giống mục 2)

- Không đưa S3 I/O vào writer transaction; promote ghi-then-verify như `publish_atomic`.
- Không ghi đè payload khác; idempotent; retry an toàn; không fallback local khi S3 lỗi.
- Không xoá raw; backup/lease trước khi ghi (theo `docs/MINIO_OPERATIONS.md` nếu chạm S3 thật).
- Bronze chỉ được chuyển trạng thái sau khi verify + commit; fail-closed khi thiếu gate.
- Byte-pinned (`datasets/usdm/science.py`, `resources/`) không sửa.
- Không `docker compose down -v`; migration/promote trên dữ liệu thật là thao tác có backup.

### 11.7 Phase đề xuất (tách khỏi phase 0–10)

| # | Nội dung | Exit criteria |
|---|---|---|
| P1 | Đặc tả gate G1–G6 + chốt D11–D15; viết test cho `promoter` bằng fake repo (không S3 thật) | Đơn vị công việc + gate được chốt; test gate PASS với mock |
| P2 | `promoter.py` + `climate-platform promote --once` (chưa `--watch`) | `--once` promote đúng 1 đơn vị đủ điều kiện; không đủ gate → no-op; idempotent khi chạy lại |
| P3 | `--watch` + `PROMOTE_*` trong `Settings`; wiring Compose (worker) | Vòng lặp chạy local; readiness/health không đổi; log không chứa secret |
| P4 | Real path: chạy với USDM replay thật + backup/restore drill | Bằng chứng command/ngày/test count; mock vs real tách rõ |

### 11.8 Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Race giữa promote và ingest đang ghi | Cao | Gate G2 (lease/attempt), không promote khi có writer mở; test race |
| Promote lặp tạo sản phẩm/Gold trùng | Cao | Idempotent + conditional PUT `IfNoneMatch`; unique constraints; test chạy lại |
| Điều kiện gate sai → promote thiếu nguyên liệu | Cao | G1/G4 bắt buộc; fail-closed; test thiếu dependency |
| Vô tình đụng raw/revision/ownership | Cao | Chỉ đọc qua service hiện có; không tự viết SQL; review diff |
| Thêm dịch vụ/broker ngoài phạm vi | Trung bình | Chỉ phương án A/B; kiểm tra `compose.yaml` không thêm image lạ |
| Chạy trong lúc dữ liệu thật chưa backup | Cao | Yêu cầu backup/restore drill ở P4; không promote trên dữ liệu thật khi chưa chốt |

### 11.9 Quyết định cần xác nhận (bổ sung D11–D15)

| # | Quyết định | Đề xuất mặc định |
|---|---|---|
| D11 | Đơn vị công việc để xét gate | Chốt sau khi trả lời: theo file / theo `source_date` / theo tuần |
| D12 | Cơ chế trigger | **A** (`--watch` trong worker) + **B** (`--once`) dùng chung engine gate |
| D13 | Mặc định bật/tắt | `PROMOTE_ENABLED=false` — opt-in, không tự chạy khi chưa bật |
| D14 | Phạm vi tầng đích | Chỉ promote tới mức hiện có (**Silver local + Gold/warehouse**); Silver/Gold S3 để task riêng |
| D15 | Ghi đè release cũ khi có Bronze mới | Không ghi đè tại chỗ; tạo revision/attempt mới rồi `activate` (giữ revision chain) |

### 11.10 Trạng thái

- Mục 11: **ĐỀ XUẤT, chưa đặc tả đầy đủ, chưa triển khai.** Cần trả lời D11–D15 trước khi bắt đầu P1.
- Không phụ thuộc thứ tự với refactor mục 0–10; có thể làm trước/sau, nhưng **không trộn** vào cùng
  phase/commit refactor.

---

## 12. [ĐỀ XUẤT — CHỜ DUYỆT] Chuẩn hoá tầng dữ liệu bằng SQLAlchemy + tách `entity` / `repositories` / `s3`

> Mục này là **đề xuất refactor tầng dữ liệu**, tách biệt section 0–10 (đã **DONE**) và section 11
> (feature auto-promote). **Chưa viết code.** Cần chốt **D16–D23** (mục 12.3) trước khi bắt đầu S1.
> Dependency `SQLAlchemy==2.0.36` + `alembic==1.14.0` đã thêm vào `requirements.txt` và `pyproject.toml`.

### 12.1 Mục tiêu

- Thay `sqlite3` + SQL viết tay bằng **SQLAlchemy 2.0 declarative ORM** — truy vấn hướng đối tượng,
  entity rõ ràng, một nơi khai báo schema.
- Gom **entity** và **repository** ra **cấp package** `src/climate_platform/entity/` và
  `src/climate_platform/repositories/` (thay vì rải trong `modules/*/repositories/`).
- Chuyển toàn bộ thao tác **object storage (MinIO/S3 + local Bronze)** ra
  `src/climate_platform/s3/` (thay `modules/storage/`).
- Giữ **nguyên hành vi và bất biến dữ liệu** (mục 2): không đổi HTTP contract, schema, hash/ownership/
  revision, object-key layout.

### 12.2 Non-goals

- Không gộp 4 file SQLite — giữ tách `ingestion.sqlite3`, `control.sqlite3`, `warehouse.sqlite3`,
  `access.sqlite3`.
- **Không** Prisma/TypeScript (Python client đã deprecated — đã loại từ đầu).
- Không thêm broker/DI framework/CI; không thêm tính năng nghiệp vụ mới.
- Không đổi hình dạng bảng/khóa/index/constraint đã có — chỉ **biểu diễn lại** bằng SQLAlchemy.
- Không chạm file byte-pinned (`datasets/usdm/resources/`, `datasets/usdm/science.py`).

### 12.3 Quyết định cần xác nhận (D16–D23)

| # | Quyết định | Đề xuất mặc định |
|---|---|---|
| D16 | ORM + migration | **SQLAlchemy 2.0** (declarative `Mapped[]`) + `alembic` |
| D17 | Tên folder cấp package | `entity/` · `repositories/` · `s3/` (đúng yêu cầu); có thể đổi `entity/`→`entities/` nếu muốn số nhiều |
| D18 | Số file DB | **Giữ 4** SQLite tách biệt (không gộp) |
| D19 | Quản lý schema | `initialize()` dựng schema bằng `Base.metadata` + additive `ALTER` như hiện tại; Alembic **baseline-stamp** DB có sẵn (không autogenerate phá schema) |
| D20 | Chiến lược kết nối | Giữ **connection-per-operation** (`NullPool`) + `PRAGMA`/read-only/`BEGIN IMMEDIATE`; không dùng session pool dài hạn |
| D21 | Quy ước đặt tên repo | Theo **domain** (`catalog_repository.py`, `auth_repository.py`…) thay quy ước "theo công nghệ" ở mục 4.1 — cập nhật lại plan |
| D22 | Map lỗi BUSY | Giữ map `OperationalError(BUSY/LOCKED)` → HTTP 503 ở ranh giới repository (ORM không tự nuốt) |
| D23 | Shim tương thích | **Không** shim `metadata_manager`; cập nhật atomically mọi import (theo D6) |

### 12.4 Cấu trúc thư mục đích

> Cây thư mục đích (đã gộp cả `entity/` · `repositories/` · `s3/` cấp package) nằm ở **mục 4** —
> đó là nguồn duy nhất, tránh trùng lặp. Mục 12 chỉ ghi chi tiết tầng dữ liệu (12.5–12.8).

### 12.5 Ánh xạ file hiện tại → vị trí mới

| Hiện tại | Đích |
|---|---|
| `modules/catalog/model.py::FileMetadata` | `entity/registry.py::Observation` (+ giữ `FileMetadata` như entity-view/DTO nếu cần) |
| `modules/catalog/repositories/sqlite_repository.py` (`metadata_manager`, `MetadataManager`) | `repositories/catalog_repository.py` |
| `modules/auth/repositories/user_repository.py` + `session_repository.py` | `repositories/auth_repository.py` |
| `modules/authorization/repositories/grant_repository.py` | `repositories/authorization_repository.py` |
| `modules/portal/repositories/store.py` (transient/audit/config/usage/leases) | `repositories/control_repository.py` |
| `modules/portal/repositories/releases.py` | `repositories/releases.py` |
| SQL trong `common/middleware.py` (access.sqlite3) | `repositories/access_repository.py` |
| SQL trong `datasets/usdm/processor.py` (warehouse.sqlite3) | `repositories/warehouse_repository.py` |
| `modules/storage/{module,keys}.py` + `repositories/{object,minio,local}_repository.py` | `s3/{module,keys,object_repository,minio_repository,local_repository}.py` |

### 12.6 Thiết kế SQLAlchemy (giữ đúng semantics)

- **Engine theo từng DB**, `poolclass=NullPool` (connection-per-op như hiện tại):
  `create_engine("sqlite:///" + str(db_path), poolclass=NullPool, connect_args={"timeout": busy_timeout})`.
- **Pragma qua event `connect`**: `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout`.
- **`BEGIN IMMEDIATE` cho writer**: tắt transaction ngầm của pysqlite (`isolation_level=None`) và
  `@event.listens_for(engine, "begin")` → `conn.exec_driver_sql("BEGIN IMMEDIATE")` (recipe chuẩn SQLAlchemy
  cho concurrency SQLite).
- **Engine read-only** (readiness/release/snapshot): URL `sqlite:///file:<path>?mode=ro&uri=true`.
- **Partial unique index** `one_current_revision`: `Index(..., unique=True, sqlite_where=text("is_current=1"))`.
- **CHECK/UNIQUE/FK/composite PK**: biểu diễn bằng `CheckConstraint`/`UniqueConstraint`/`ForeignKey`/
  `PrimaryKeyConstraint` — **không đổi DDL**.
- **View `gold_weekly`**: tạo bằng DDL tường minh trong `initialize()` (SQLAlchemy không map view tự động).
- **`executemany`/raw**: dùng `Connection.exec_driver_sql` / `text()` cho maintenance (giữ nguyên câu lệnh).
- **`db.backup()`**: `conn.connection.driver_connection.backup(target)` (giữ SQLite backup API, không copy bỏ WAL).
- **Map lỗi**: `sqlalchemy.exc.OperationalError`/`sqlite3.OperationalError` BUSY/LOCKED → HTTP 503 tại
  `repositories/database.py`.

### 12.7 Entity theo từng DB

- **ingestion.sqlite3** — `Observation` (PK `file_id`; FK `sha256`→`ContentBlob`, `previous_file_id`→self;
  UNIQUE `(source,source_date,dataset_key,sha256)` và `(…,revision)`; partial index `one_current_revision`;
  index `observation_owner`), `ContentBlob` (PK `sha256`), `RecoveryReport`. Giữ `PRAGMA user_version=1`.
- **control.sqlite3** — `User` (PK `user_id`, UNIQUE `username`), `Session` (PK `token`, FK `user_id`),
  `Grant` (PK `(user_id,dataset_id,layer)`), `Transient`, `Audit` (PK autoincrement), `Config` (PK `key`),
  `PortalUsage` (PK `(user_id,category)`), `Lease`.
- **warehouse.sqlite3** — `Build` (PK `build_id`), `Attempt` (PK autoincrement), `GoldCell`
  (PK `(build_id,grid)`, FK `build_id`, CHECK `drought IN ('0','D0','D1','D2','D3','D4')`), view `gold_weekly`.
- **access.sqlite3** — `AccessUsage` (PK `key_id`, `minute/requests/day/bytes`).

### 12.8 Bất biến phải giữ (như mục 2 + 4.2)

- HTTP contract, `dataset_key` optional/fallback, `200 VERIFIED/DUPLICATE`, `metadata.status`, `file_id`,
  ownership, revision chain, object-key layout, hash semantics: **không đổi**.
- Không S3 I/O trong writer transaction; conditional PUT `IfNoneMatch="*"`; orphan adoption; fail-closed;
  không fallback local khi S3 lỗi.
- SQLite: connection riêng mỗi op, transaction/unique/partial-index giữ nguyên; không đặt active DB lên NFS.
- Backup/restore giữ qua SQLite backup API (`s3_maintenance`, `release.snapshot`, `scripts/backup/*`).
- Không sửa file byte-pinned.

### 12.9 Phase đề xuất (giữ app chạy được sau mỗi phase)

| # | Nội dung | Exit criteria |
|---|---|---|
| S0 | Baseline: `ruff` + `pytest -q` + snapshot `openapi.json`; backup `.agents/temp/refactor-db/` | PASS + snapshot ghi lại |
| S1 | `entity/base.py` + `repositories/database.py` (engine/pragma/read-only/BEGIN IMMEDIATE) | Unit test WAL/synchronous/FK/BUSY→503 đúng |
| S2 | `entity/registry.py` + `repositories/catalog_repository.py`; cập nhật `catalog/{service,module,maintenance,s3_maintenance}.py`, `system/readiness.py` | `tests/api/test_stage2_registry.py`, `tests/backup/*` PASS |
| S3 | `s3/` (dời `modules/storage`) + cập nhật `datasets/usdm/processor.py`, scripts, tests | `tests/infrastructure/test_s3_keys.py` + smoke fixture PASS |
| S4 | `entity/control.py` + `repositories/{auth,authorization,control}_repository.py`, `releases.py` | `tests/portal/test_portal.py`, `tests/release/test_stage5_release.py` PASS |
| S5 | `entity/{access,warehouse}.py` + `repositories/{access,warehouse}_repository.py` (`common/middleware.py`, `usdm/processor.py`) | `tests/api/test_server.py`, `tests/api/test_readiness_security.py`, `tests/usdm/*` PASS |
| S6 | (tuỳ chọn) Alembic baseline-stamp 4 DB có sẵn; xoá `modules/storage/` + `*/repositories/` cũ; cập nhật docs (`AGENTS.md`, `docs/AGENT_MODULES.md`) + mục 4 plan này | OpenAPI diff = 0; ruff + pytest PASS |

### 12.10 Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| BEGIN IMMEDIATE bị pysqlite nuốt BEGIN → race writer | Cao | Tắt transaction ngầm (`isolation_level=None`) + event `begin`; test concurrent |
| ORM tự bọc transaction / bỏ unique constraint | Cao | Giữ connection-per-op; khai báo unique/partial index trong metadata; test duplicate/revision |
| Đổi DDL ngầm (CHECK/FK/index) | Cao | So `.schema`/`PRAGMA` trước–sau; giữ `user_version` |
| Alembic autogenerate phá DB thật | Cao | Chỉ **baseline-stamp**; migration thật cần backup + target rõ |
| Bỏ sót call site (tests/scripts/Docker) | Trung bình | Inventory ở S0 + `grep` mỗi phase |
| Read-only engine mở nhầm write | Trung bình | URL `mode=ro`; test readiness không tự tạo DB |

**Rollback:** mỗi phase một commit độc lập trên nhánh riêng; không `docker compose down -v`; không sửa
dữ liệu thật khi chưa backup.

### 12.11 Trạng thái

- **DONE** (2026-11-24, Asia/Saigon). Đã thực hiện S1–S5; S6 (Alembic baseline-stamp) **chưa làm** —
  schema vẫn dựng bằng `Base.metadata` + additive `ALTER`, giữ `PRAGMA user_version`.
- **Cấu trúc:** `entity/` (`base` + `registry`/`control`/`warehouse`/`access`), `repositories/`
  (`database` + `catalog`/`auth`/`authorization`/`control`/`access`/`warehouse`_repository + `releases`),
  `s3/` (`object`/`minio`/`local`_repository + `keys` + `module`). Đã xoá `modules/storage/` và mọi
  `modules/*/repositories/` (`catalog`, `auth`, `authorization`, `portal`).
- **Bất biến giữ nguyên:** connection-per-op (`NullPool`), WAL/`synchronous=FULL`/FK, read-only
  (`mode=ro`), `BEGIN IMMEDIATE`, busy→503, partial index `one_current_revision`, object-key layout,
  revision/ownership, SQLite backup API.
- **Bằng chứng (2026-11-24):**
  - `ruff check --no-cache .` → All checks passed; `ruff format --check --no-cache .` → 146 files formatted.
  - `pytest -q` (tests/api, backup, infrastructure, portal, release, config, usdm; `TMPDIR` trong
    `.agents/temp/pytest-tmp`): **114 passed, 5 skipped, 3 failed** — khớp baseline; 3 fail là lỗi môi
    trường macOS (reader subprocess + `/var` symlink), không do refactor.
  - Không chạy: `tests/integration/test_loopback.py` (thiếu sibling Client), MinIO/Compose smoke, GIS thật.
- **Ghi chú thi hành:** catalog dùng ORM entity (`select(Entity)`/`insert`); các repository còn lại chạy
  SQL hiện hữu qua một connection adapter SQLAlchemy (`repositories/database.py::DatabaseConnection`)
  để giữ đúng transaction/`BEGIN IMMEDIATE` semantics; `connection()` **không** auto-commit (như
  `MetadataManager.connection()` gốc), còn `Store.db()`/`warehouse_repository.db()` commit khi thành công.
