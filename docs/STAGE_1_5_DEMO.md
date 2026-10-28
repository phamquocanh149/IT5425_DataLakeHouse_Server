# Demo Stage 1.5 ? 5?7 ph?t

Ki?n tr?c: m?t Client g?i nhi?u ngu?n t?i m?t Server. Mock nh?, kh?ng t?i NASA/USGS.
Chu?n b? hai th? m?c c?nh nhau: `climate-platform`, `climate-collector`, ?? c?i dependencies.
C?c l?nh demo d?ng loopback c?ng m?y; v?i hai m?y thay SERVER_BASE_URL b?ng HTTPS Tailscale.

## Chu?n b? tr??c bu?i demo

T?o `.env` t? `.env.example` n?u ch?a c?, kh?ng ghi ?? c?u h?nh ?ang d?ng.
Server: ?i?n COLLECTOR_API_KEY v? ADMIN_API_KEY kh?c nhau.
Client: CLIENT_ID=collector01, CLIENT_ROLE=all, SERVER_API_KEY b?ng Collector key,
SERVER_BASE_URL=http://127.0.0.1:8000. Kh?ng nh?p key v?o Git ho?c log.
N?u c? JSON l?ch s?, ch?y migration v? xem report tr??c demo; kh?ng c?n cho d? li?u m?i.

## 1. Kh?i ??ng Server (terminal A, ~30s)

```powershell
cd climate-platform
$env:DEBUG='False'
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

## 2. Health v? upload USDM (terminal B, ~1 ph?t)

```powershell
cd climate-collector
.\.venv\Scripts\python.exe scripts/check_server.py
.\.venv\Scripts\python.exe scripts/generate_sample.py --source usdm
.\.venv\Scripts\python.exe scripts/send_file.py --file data/pending/sample_usdm.csv --source usdm --date 2021-06-22 --dataset-key demo/usdm
```

K? v?ng l?n ??u: HTTP 200, server_status VERIFIED, listing_check matched; job chuy?n
sang data/uploaded. File mock ngu?n v?n ? data/pending; ??y kh?ng ph?i pending job.
N?u demo ?? ch?y tr??c ??, DUPLICATE l? h?p l?; d?ng ng?y demo m?i n?u c?n observation m?i.

## 3. Xem Bronze v? SQLite (terminal C, ~1 ph?t)

```powershell
cd climate-platform
Get-ChildItem data_lake/bronze -Recurse -File
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('metadata/ingestion.sqlite3'); print(c.execute('SELECT file_id,client_id,source,source_date,dataset_key,revision,status FROM observations').fetchall()); c.close()"
.\.venv\Scripts\python.exe scripts/reconcile_storage.py --checksum
```

B?n ghi collector01/usdm; checksum trong SQLite kh?p raw. Kh?ng s?a/x?a d? li?u ?? l?m demo.

## 4. NOAA v? duplicate (terminal B, ~1 ph?t)

```powershell
.\.venv\Scripts\python.exe scripts/send_file.py --file data/pending/sample_usdm.csv --source noaa --date 2021-06-22 --dataset-key demo/noaa
.\.venv\Scripts\python.exe scripts/send_file.py --file data/pending/sample_usdm.csv --source usdm --date 2021-06-22 --dataset-key demo/usdm
```

NOAA l? observation m?i d? bytes gi?ng USDM. G?i l?i USDM tr? DUPLICATE v? c?ng file_id;
kh?ng th?m observation. M?i l?nh th? c?ng l? job m?i; retry worker ? b??c sau gi? c?ng job.

## 5. Offline ? pending ? ph?c h?i (1?2 ph?t)

Terminal A: Ctrl+C d?ng Server. Terminal B:

```powershell
.\.venv\Scripts\python.exe scripts/send_file.py --file data/pending/sample_usdm.csv --source usdm --date 2021-06-23 --dataset-key demo/usdm
Get-ChildItem data/pending -Directory | ForEach-Object { Get-Content (Join-Path $_.FullName 'metadata.json') }
```

K? v?ng upload b?o l?i, payload c?n nguy?n, state RETRY_PENDING, attempts/deadline ???c l?u.
Kh?i ??ng l?i Server b?ng l?nh ? b??c 1. Terminal B:

```powershell
.\.venv\Scripts\python.exe scripts/retry_pending.py --watch --interval 10
```

Ch? deadline backoff ??n h?n (v?i c?u h?nh m?c ??nh th??ng t?i ?a v?i ch?c gi?y ? demo).
K? v?ng report uploaded ch?a ??ng job_id c?, t?n file g?c gi? nguy?n, snapshot chuy?n
sang uploaded, SQLite th?m observation ng?y 2021-06-23. Ctrl+C d?ng worker.
C? th? d?ng `--once` sau deadline ?? g?i m?t l??t, kh?ng ch?y watch.

## 6. Ki?m tra k?t th?c (~30s)

Ch?y l?i c?u SQL v? reconcile ? b??c 3: quan s?t kh?c ng?y, c?ng blob checksum;
kh?ng c? metadata tr?ng logical identity. Xem `data/source_status.json` ph?a Client.
Kh?ng ??nh ??ng VERIFIED v?i Silver/Gold. Kh?ng b?t scheduler/service trong demo.

## Ki?m th? t? ??ng t??ng ???ng

Trong Server, repo Client b?n c?nh:

```powershell
$env:CLIENT_REPO_PATH=(Resolve-Path ..\climate-collector).Path
.\.venv\Scripts\python.exe -m pytest tests/integration -q
```

S?u k?ch b?n A?F c? storage/credentials t?m v? HTTP loopback th?t; F d?ng hai subprocess
Client ??ng th?i. ??y kh?ng ph?i b?ng ch?ng ?? ch?y qua hai m?y Windows/Tailscale.
