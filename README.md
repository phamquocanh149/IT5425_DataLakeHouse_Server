# Climate Data Lake Platform — Phase 1: Server & Bronze Ingestion

Hệ thống **Distributed Climate Data Lake Server** được thiết kế theo kiến trúc **Medallion (Bronze → Silver → Gold)** nhằm tiếp nhận, xác thực, và lưu trữ dữ liệu nghiên cứu hạn hán Hoa Kỳ (US Drought Monitor, NOAA, NASA NLDAS-2, USGS).

- **Paper tham khảo**: [Nature Scientific Data (2024)](https://doi.org/10.1038/s41597-024-03202-6)
- **Repository tham khảo**: [USDMdata](https://github.com/heplersa/USDMdata)

---

## 1. Kiến trúc hệ thống & Luồng dữ liệu

```
[ Client 01: USDM / NOAA ]   ---+
                                 +---> [ Tailscale / LAN HTTPS ] ---> [ Climate Data Lake Server (FastAPI) ]
[ Client 02: NLDAS / USGS ]  ---+                                            |
                                                                              +---> [ Streaming Chunk Upload (<= 20MB) ]
                                                                              +---> [ In-flight SHA-256 Checksum ]
                                                                              +---> [ Sanitize Filename / Anti-Path Traversal ]
                                                                              +---> [ Deduplication Check ]
                                                                              +---> [ Atomic Relocate to Bronze Layer ]
                                                                              +---> [ Atomic JSON Metadata Record ]
```

### Cấu trúc lưu trữ Bronze Layer:
```
data_lake/bronze/{source}/ingestion_date=YYYY-MM-DD/sha256={checksum}/{original_filename}
```
- `source`: Danh mục nguồn dữ liệu hợp lệ (`usdm`, `noaa`, `usgs`, `nldas`).
- `ingestion_date`: Ngày server tiếp nhận dữ liệu (UTC YYYY-MM-DD). Phân biệt với `source_date` (ngày quan trắc / phát hành).
- `sha256`: Mã băm SHA-256 tính toán phía server, dùng để định danh phân vùng và chống trùng lặp dữ liệu.

---

## 2. Cấu trúc thư mục dự án

```
IT5425_DataLakeHouse_Server/
├── server/
│   ├── __init__.py           # Package init
│   ├── main.py               # FastAPI application, routes (/health, /upload, /uploads)
│   ├── config.py             # Pydantic Settings, đường dẫn lưu trữ, API keys map
│   ├── ingestion.py          # Streaming chunk upload, SHA-256, atomic move, deduplication
│   ├── metadata.py           # Atomic JSON metadata persistence & query manager
│   └── security.py          # Xác thực API Key qua X-API-Key header, xác định client_id
├── data_lake/
│   ├── bronze/               # Bronze Lake - Dữ liệu thô nguyên bản không sửa đổi
│   │   ├── usdm/
│   │   ├── noaa/
│   │   ├── usgs/
│   │   └── nldas/
│   ├── silver/               # Thư mục chuẩn bị cho giai đoạn chuyển đổi Parquet
│   └── temp/                 # Thư mục tạm cho quá trình upload streaming
├── warehouse/                # Thư mục chuẩn bị cho Gold Layer (DuckDB / dbt)
├── metadata/                 # Lưu trữ metadata dạng JSON cho từng file được ingest
├── scripts/
│   └── test_upload.py        # CLI script gửi file thử nghiệm lên server & xem metadata
├── tests/
│   ├── __init__.py
│   └── test_server.py        # Bộ kiểm thử pytest tự động (10 test cases)
├── .env.example              # Cấu hình mẫu môi trường
├── .env                      # Cấu hình biến môi trường cục bộ
├── .gitignore                # Bỏ qua venv, cache, file tạm dữ liệu lớn
├── pytest.ini                # Cấu hình pytest
├── requirements.txt          # Danh sách thư viện Python cần thiết
└── README.md                 # Tài liệu hướng dẫn chi tiết
```

---

## 3. Cài đặt và kích hoạt môi trường

### Yêu cầu:
- Windows 10/11 (Đã kiểm tra trên máy 16GB RAM)
- Python 3.11 hoặc 3.12 (Hệ thống đã cài đặt Python 3.11.0)

### Clone và tạo Virtual Environment:
Mở PowerShell và chạy:
```powershell
git clone https://github.com/phamquocanh149/IT5425_DataLakeHouse_Server.git
cd IT5425_DataLakeHouse_Server
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Điền `CLIENT01_API_KEY`, `CLIENT02_API_KEY` và `ADMIN_API_KEY` trong `.env` bằng
các khóa riêng biệt do bạn tạo; cấp khóa Client tương ứng cho từng máy.
Các khóa mặc định để trống, nên API có xác thực sẽ từ chối request cho đến khi cấu hình.
Không commit `.env`. Tests dùng khóa giả độc lập, không cần credentials thật.

### Kích hoạt Virtual Environment (tùy chọn):
```powershell
.\.venv\Scripts\Activate.ps1
```

*(Nếu gặp lỗi PowerShell ExecutionPolicy, mở PowerShell thông thường và chạy: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### Cài đặt lại thư viện (nếu cần):
```powershell
pip install -r requirements.txt
```

---

## 4. Khởi chạy Server

Chạy lệnh Uvicorn trên `127.0.0.1:8000` (theo đúng nguyên tắc bảo mật, không binding ra `0.0.0.0` khi chưa ủy quyền):

```powershell
uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
```

Truy cập kiểm tra:
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Interactive API Docs (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative Docs (ReDoc)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 5. Danh sách API Endpoints

### 1. `GET /health`
- **Mục đích**: Kiểm tra tình trạng hoạt động của server.
- **Xác thực**: Không yêu cầu.
- **Response mẫu**:
  ```json
  {
    "status": "ok",
    "service": "climate-data-server"
  }
  ```

### 2. `POST /upload`
- **Mục đích**: Nhận file dữ liệu khí hậu bằng `multipart/form-data`.
- **Headers**:
  - `X-API-Key: <client_api_key>` (Bắt buộc).
- **Form Data**:
  - `file`: File nhị phân/văn bản (tối đa 20MB).
  - `source`: Một trong các giá trị: `usdm`, `noaa`, `usgs`, `nldas`.
  - `source_date`: Ngày quan trắc định dạng `YYYY-MM-DD`.
- **Response mẫu (Upload mới thành công)**:
  ```json
  {
    "status": "VERIFIED",
    "message": "File ingested and verified successfully into Bronze Data Lake",
    "metadata": {
      "file_id": "file_10490607d26742b5",
      "source": "usdm",
      "source_date": "2021-06-22",
      "client_id": "client01",
      "original_filename": "usdm_sample.csv",
      "stored_path": "data_lake/bronze/usdm/ingestion_date=2026-10-09/sha256=e0d9f2f.../usdm_sample.csv",
      "size_bytes": 310,
      "sha256": "e0d9f2f7bcc04f8a509fe1c2fb75d3dc61563529625f69b100612bd4f653f63a",
      "received_at": "2026-10-09T17:01:56Z",
      "status": "VERIFIED"
    }
  }
  ```
- **Response mẫu (Phát hiện trùng lặp Checksum)**:
  ```json
  {
    "status": "DUPLICATE",
    "message": "File with identical SHA-256 already exists in Bronze Data Lake",
    "metadata": { ... }
  }
  ```

### 3. `GET /uploads`
- **Mục đích**: Lấy danh sách file đã tiếp nhận và metadata.
- **Headers**:
  - `X-API-Key: <client_api_key>` (Bắt buộc).
- **Query Params**:
  - `source`: Lọc theo nguồn (tùy chọn: `usdm`, `noaa`, `usgs`, `nldas`).

---

## 6. Hướng dẫn chạy thử nghiệm Client Upload

Script tiện ích `scripts/test_upload.py` được cung cấp sẵn để kiểm tra gửi dữ liệu từ dòng lệnh:

### 1. Upload một file mẫu tự tạo:
```powershell
python scripts\test_upload.py --source usdm --source-date 2021-06-22
```

### 2. Upload một file có sẵn từ đĩa:
```powershell
python scripts\test_upload.py --file "path\to\climate_data.zip" --source noaa --source-date 2021-06-23
```

### 3. Kiểm tra tính năng Deduplication:
Chạy lại cùng một lệnh trên. Server sẽ tự động phát hiện mã băm SHA-256 trùng khớp, trả về trạng thái `DUPLICATE` và không tạo bản sao thừa trên đĩa.

### 4. Truy vấn danh sách các file đã upload:
```powershell
python scripts\test_upload.py --list --source usdm
```

---

## 7. Chạy kiểm thử tự động (pytest)

Toàn bộ 10 kịch bản kiểm thử bắt buộc đã được cài đặt và vượt qua 100%:

```powershell
pytest
```

**Các kịch bản kiểm thử:**
1. Khởi động server & kiểm tra `GET /health` trả về HTTP 200.
2. Upload file CSV hợp lệ thành công và kiểm tra lưu trữ Bronze.
3. Mã SHA-256 của file đã lưu khớp chính xác với file gốc.
4. Metadata JSON được tạo đầy đủ và chính xác với trạng thái `VERIFIED`.
5. Upload lại file giống hệt trả về `DUPLICATE`, không tạo file trùng lặp.
6. Từ chối nguồn dữ liệu không hợp lệ (`source != usdm/noaa/usgs/nldas`).
7. Từ chối định dạng ngày `source_date` sai quy chuẩn `YYYY-MM-DD`.
8. Từ chối file vượt quá giới hạn 20MB (HTTP 413).
9. Từ chối API Key thiếu hoặc không hợp lệ (HTTP 401).
10. Chống tấn công Path Traversal (`../../filename`), đảm bảo file không thoát khỏi thư mục Bronze.
11. Ngắt kết nối giữa chừng tự động dọn dẹp file tạm và không tạo metadata `VERIFIED`.
12. Truy vấn `GET /uploads` có xác thực và lọc theo source.

---

## 8. Hướng dẫn kết nối Client 01 & Client 02 qua Tailscale Serve

Để hai máy Client truyền dữ liệu an toàn đến Server Windows mà **không cần**:
- Mở port modem / router (Port Forwarding),
- Thay đổi cấu hình Windows Firewall,
- Expose server ra public Internet qua `0.0.0.0`:

### Quy trình đề xuất:
1. Cài đặt [Tailscale](https://tailscale.com/) trên cả 3 máy (Server, Client 01, Client 02) và đăng nhập cùng một Tailnet.
2. Trên máy Server Windows, server giữ nguyên lắng nghe tại `127.0.0.1:8000`.
3. Bật tính năng **Tailscale Serve** trên máy Server:
   ```powershell
   tailscale serve --bg 8000
   ```
   Tailscale sẽ cung cấp một tên miền nội bộ có chứng chỉ SSL HTTPS hợp lệ, ví dụ:
   `https://windows-server.tailnet-xyz.ts.net`
4. Trên Client 01 & Client 02, cấu hình URL gửi dữ liệu:
   - Client 01 (USDM, NOAA) dùng khóa `CLIENT01_API_KEY` bạn đã cấu hình.
   - Client 02 (NLDAS-2, USGS) dùng khóa `CLIENT02_API_KEY` bạn đã cấu hình.
   - Gửi HTTPS tới: `https://windows-server.tailnet-xyz.ts.net/upload`
5. Kết nối qua mạng Tailscale được mã hóa; quyền truy cập phụ thuộc cấu hình Tailnet và API key.
