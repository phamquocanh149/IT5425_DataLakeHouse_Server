Đã kiểm tra trạng thái hiện tại: `api` + `minio` đang healthy, key client khớp server, portal release `usdm-stage3-v1` và `frontend-climate-platform/dist` đã sẵn, nhưng cổng 8010 chưa chạy. Lưu ý: OS đang có `DEBUG=release`, nên các script Python native phải set `$env:DEBUG='False'` (nếu không Pydantic báo lỗi boolean).

**1. Server + MinIO** (hiện đã chạy, chỉ cần kiểm tra):
```powershell
cd 'D:\Trực quan hóa\DataLake_Warehouse\climate-platform'
docker compose up -d --build --wait --wait-timeout 120
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

**2. Client gửi file vào Bronze**:
```powershell
cd 'D:\Trực quan hóa\DataLake_Warehouse\climate-collector'
.\.venv\Scripts\python.exe scripts/check_server.py
.\.venv\Scripts\python.exe scripts/generate_sample.py --source usdm
.\.venv\Scripts\python.exe scripts/send_file.py --file data/pending/sample_usdm.csv --source usdm --date 2021-06-22 --dataset-key demo/usdm
```
Kỳ vọng `VERIFIED`; gửi lại cùng nội dung sẽ là `DUPLICATE`.

**3. Portal** (API + frontend cùng cổng 8010):
```powershell
cd 'D:\Trực quan hóa\DataLake_Warehouse\climate-platform'
$env:DEBUG='False'
.\.venv\Scripts\python.exe scripts/portal/run_portal_demo.py
```
Mở http://127.0.0.1:8010/portal/ và chọn tài khoản demo (Minh Anh, Hoàng Nam, Quản trị, Khách). Tôi đã smoke test: `/portal/` trả HTTP 200 và demo IdP hoạt động. Nếu vừa sửa UI thì build lại trước:
```powershell
npm.cmd --prefix ../frontend-climate-platform run build
```

**Lưu ý quan trọng**
- File gửi ở bước 2 chỉ vào Bronze + SQLite của API Docker; **không tự chạy Silver/Gold và không tự xuất hiện trên Portal**. Portal đang phục vụ release Stage 3 có sẵn từ `.test-runs/usdm-stage3`.
- Muốn làm mới dữ liệu Portal phải chạy lại Stage 3 rồi `prepare_portal.py --verify` và `--activate`. `.venv` hiện là Python 3.11, không có GeoPandas/PyArrow; dùng image worker `climate-phase1-worker:closeout` (Python 3.14 + `requirements-gis.txt`) hoặc venv GIS riêng, không dùng Anaconda.
- Frontend thật là `frontend-climate-platform`; thư mục `climate-platform/frontend` chỉ còn file cũ, không phải UI đang chạy.

Chạy mục 1–3 là đủ để demo end-to-end với dữ liệu hiện có.