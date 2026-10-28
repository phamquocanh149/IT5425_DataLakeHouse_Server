# Stage 1.5 API contract

## Endpoints

`GET /health`: public; HTTP 200 `{ "status": "ok", "service": "climate-data-server" }`.
`GET /openapi.json`: FastAPI schema, kh?ng b?t bu?c d?ng ?? g?i file.

`POST /upload`: header `X-API-Key`, multipart:

| Field | Required | ? ngh?a |
|---|---|---|
| file | C? | File raw kh?ng r?ng, m?c ??nh <=20 MiB |
| source | C? | usdm/noaa/usgs/nldas |
| source_date | C? | YYYY-MM-DD |
| dataset_key | Kh?ng | Stable product/station/indicator key, <=512 k? t?, kh?ng control chars |

Thi?u dataset_key th? d?ng basename filename g?c; field tr?ng ???c FastAPI xem nh? thi?u.
Kh?ng d?ng dataset_key ho?c filename ?? ?i?u khi?n ???ng d?n raw. Kh?ng g?i client_id;
Server l?y identity t? key. Collector m?i g?i dataset_key r? r?ng, field c? gi? nguy?n.

HTTP 200:

```json
{
  "status": "VERIFIED",
  "message": "Bronze and registry committed",
  "metadata": {
    "file_id": "file_<id>",
    "client_id": "collector01",
    "source": "usdm",
    "source_date": "2021-06-22",
    "dataset_key": "usdm/demo",
    "original_filename": "sample.csv",
    "stored_path": "data_lake/bronze/usdm/sha256=<hash>/payload",
    "sha256": "<64 hexadecimal characters>",
    "size_bytes": 78,
    "received_at": "<UTC timestamp>",
    "status": "VERIFIED",
    "revision": 1,
    "previous_file_id": null,
    "is_current": true,
    "error_message": null
  }
}
```

Response duplicate c? top-level `status=DUPLICATE`, c?ng file_id c?a logical observation
?? t?n t?i; metadata.status v?n VERIFIED. Retry revision c? c? is_current=false,
kh?ng thay ??i current. N?i dung kh?c tr?n c?ng source/date/key t?o revision m?i.
C?ng hash kh?c ng?y/source/key t?o observation m?i nh?ng c? th? d?ng chung blob.
N?u dataset thu?c identity kh?c, tr? 403, kh?ng tr? metadata qua ???ng duplicate.

`GET /uploads`: X-API-Key, optional query source; response list metadata gi? ??nh d?ng
c?. Collector ch? xem c?a m?nh v? ngu?n ???c cho ph?p; Admin xem t?t c?, g?m MISSING,
CORRUPT sau reconciliation. Ch?a c? pagination; l?u ? khi m? r?ng volume.

## Errors v? retry

| HTTP | H?nh vi |
|---|---|
| 400 | Source/date/dataset/file sai, file r?ng; kh?ng retry |
| 401 | Key thi?u/sai; kh?ng retry |
| 403 | Key h?p l? nh?ng kh?ng c? quy?n; kh?ng retry |
| 413 | V??t file-size limit; kh?ng retry |
| 422 | Multipart/validation thi?u field; kh?ng retry |
| 503 | Content ?ang c?n reconciliation; retry gi?i h?n, sau ?? c?n ng??i v?n h?nh |
| 500 | L?i storage/database b?t ng?; kh?ng c? VERIFIED, Client retry gi?i h?n |

Client c?n retry network/timeout/408/429/502/504 theo budget. HTTP 409 kh?ng ph?i
success ho?c duplicate contract. Retry m?t logical identity ???c unique constraint
b?o v?. Kh?ng t?o endpoint /register, /verify ho?c /ingest.

## Migration compatibility

Client Phase 1 g?i ba field v?n d?ng ???c v?i Collector key m?i. Metadata response
ch? th?m field, status v? endpoint kh?ng ??i. Legacy key ch? b?t c? ch? ??ch b?ng
ENABLE_LEGACY_KEYS; kh?ng b?t t? ??ng. T?n file kh?c nay m?c ??nh l? dataset kh?c:
mu?n dedup qua filename kh?c ph?i g?i c?ng dataset_key ?n ??nh.

JSON l?ch s? ???c migrate ri?ng, gi? client_id v? ???ng d?n raw g?c. N?u metadata c?
ch? c?n t?n ?? sanitize, kh?ng th? suy ra t?n unsanitized: fallback dataset_key d?ng
original_filename l?u trong JSON. C?n g?i key ?? khi mu?n nh?m ??ng observation c?,
v? d?ng identity/quy?n ph? h?p; kh?ng t? ??i ownership l?ch s?.
