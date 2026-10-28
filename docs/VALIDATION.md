# Validation Stage 1.5 ? 2026-10-29

## K?t qu? ?? ch?y

| Suite | Baseline | Final |
|---|---:|---:|
| Server unit | 10 PASS | 21 PASS |
| HTTP loopback integration | Ch?a c? | 6 PASS |
| Client unit/worker | 34 PASS | 48 PASS |
| T?ng | 44 PASS | **75 PASS / 0 FAIL** |

L?n cu?i: Server `python -m pytest -q`: **27 passed, 1 warning in 17.09s**;
Client: **48 passed in 1.78s**. Python 3.11.0; d?ng c?c virtual environment hi?n c?.
C?nh b?o FastAPI/Starlette TestClient deprecate backend httpx; kh?ng c? test th?t b?i.
Ch?a thay dependency sang httpx2 v? Client y?u c?u HTTPX v? c?c test hi?n ch?y ???c.

HTTP integration th?c s? kh?i ??ng Uvicorn tr?n 127.0.0.1 v? d?ng Client HTTPX:
A upload/hash/storage, B duplicate, C c?ng bytes kh?c ng?y, D stop/restart Server v? worker
ph?c h?i c?ng job, E c? b?n source, F hai subprocess Client g?i ??ng th?i. M?i test d?ng
storage/SQLite/credentials t?m, c? cleanup process. Kh?ng d?ng kh?a th?t ?? authenticate.
Kh?ng tuy?n b? ?? ki?m th? tr?n hai m?y v?t l?/Tailscale.

B? sung ki?m th?: SQLite unique constraints/revisions/WAL, auth/authorization/visibility,
legacy multipart, JSON migration backup/idempotency/missing-file, file-publish failure,
DB insertion/commit failure v? retry nh?n l?i orphan, missing/corrupt/temp reconciliation;
Client restart/budget/backoff/permanent errors, hai worker c?ng job, OS lock ???c gi?i
ph?ng khi subprocess b? kill, acknowledgement ?? l?u nh?ng ch?a rename, checksum sai,
legacy metadata, filename, source config v? redaction secrets.

Test c? ??i c? ch? ??ch: metadata JSON m?i th?nh SQLite; duplicate filename kh?c nay
l? dataset kh?c n?u kh?ng g?i dataset_key; test duplicate d?ng filename ?n ??nh.
C?c test c? c?n h?p l? ???c gi? l?i.

CLI --help c?a send_file/retry_pending ch?y ???c. Git diff --check s?ch; ignore .env,
venv, raw, SQLite, pending, lock files; source scan kh?ng t?m th?y m?u kh?a c?/hardcoded
GitHub token/private key. ??y l? ki?m tra c? b?n, kh?ng ph?i security audit to?n di?n.

## Acceptance criteria

| Ti?u ch? | Tr?ng th?i / b?ng ch?ng |
|---|---|
| M?t Collector b?n ngu?n | PASS ? unit auth + integration E |
| Authentication v? authorization | PASS ? 401/403, own metadata, admin visibility |
| HTTP truy?n file v? Bronze nguy?n v?n | PASS ? integration A, hash/byte comparison |
| SQLite metadata ch?nh x?c | PASS ? registry/unit + integration query |
| Kh?ng m?t observation kh?c ng?y | PASS ? integration C |
| Retry kh?ng tr?ng logic | PASS ? unique constraints, integration B/F |
| Pending t?n t?i qua restart | PASS ? worker restart + integration D |
| Offline kh?ng m?t d? li?u; ph?c h?i g?i l?i | PASS ? integration D |
| Ph?t hi?n storage inconsistency | PASS ? reconciliation tests |
| Unit v? HTTP integration ???c ch?y | PASS ? 75 tests |
| README v? .env.example ki?n tr?c m?i | DONE |
| Demo Windows | DONE ? docs/STAGE_1_5_DEMO.md |

Stage 1.5 ho?n th?nh ? m?c code v? m?i tr??ng ki?m th? loopback. C?c b??c tri?n khai
th?t c?n NOT COMPLETED: c?p Collector key m?i v?o .env, migrate JSON th?c t? (n?u c?),
smoke test tr?n hai m?y/Tailscale. Kh?ng th?c hi?n c?c b??c n?y t? ??ng trong nhi?m v?.
Stage 2 Historical Replay/Live Collectors v? Stage 3 Silver/Gold: NOT IMPLEMENTED.
