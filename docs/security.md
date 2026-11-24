# Readiness and Internet deployment

`GET /livez` is process liveness only. `GET /readyz` and the compatibility alias
`GET /health` return 200 with `status=ok` or 503 with `status=unavailable`.
The collector and Docker use `/readyz`. SQLite probes run SELECT 1, read the
registry and quota database and acquire/roll back writer transactions; a missing database is never
recreated by a probe. S3 uses HeadBucket. Probes run outside the event loop,
with SQLite/S3 timeouts of 0.5 seconds, no SDK retries and a per-process 3-second
cache (both successes and failures). Alert on sustained 503; allow for cache TTL.
Lifespan startup fails on inaccessible storage, disabled versioning, unreadable
bucket policy or a resource Allow policy. The MinIO init identity grants policy
and versioning inspection, but no policy mutation to ingestion. Run the updated
init job before starting the updated API. DNS/OS stalls are outside SDK socket
timeout guarantees; deploy with reliable local DNS and an external probe timeout.

## Credentials and rotation

Run `python scripts/ops/create_api_key.py collector-2026-11` in a private terminal.
It prints a `key_id.secret` client credential and a SHA-256 server record. Use
32-byte random secrets; hashes are not password storage for human-chosen secrets.
Put records in the JSON `API_KEYS` setting. Records require `key_id`, `secret_hash`,
`client_id`, `role`, timezone-aware `expires_at`, and collector `sources`.
Optional `not_before` and `enabled=false` control activation/revocation.
For administrators use `--role admin --client-id admin`.

To rotate: add a second record with a new key ID and the same client ID/permissions,
restart the API, update collector SERVER_API_KEY, verify successful uploads, then
remove/disable the old record and restart. Both records work during overlap;
ownership, deduplication and revision history remain unchanged. Disable old keys
before expiry if compromised. Configuration is loaded at process start, not hot-reloaded.

`ENABLE_STATIC_KEYS=True` preserves existing installations during migration.
Set it to False after migration. For Internet deployment with `compose.yaml`, set
`ENABLE_STATIC_KEYS=false` and supply expiring hashed records in `API_KEYS`.
API startup rejects an empty key list when static keys are disabled. `ENABLE_LEGACY_KEYS` only
controls the older client01/client02 identities, independently of static-key mode.
Secret verification uses `hmac.compare_digest` on fixed-length hashes.

Authentication runs before multipart parsing. Persistent SQLite accounting applies
`RATE_LIMIT_PER_MINUTE` (default 120) and `DAILY_UPLOAD_QUOTA_BYTES` (default 1 GiB)
to both key ID and client ID. Rotation cannot reset the client budget. Limits are
atomic across API processes sharing the metadata volume. Quota counts received
multipart bytes, including overhead and unsuccessful/retried uploads; UTC midnight
resets the daily window. 429 includes Retry-After; accounting failure returns 503.
Keep the metadata volume persistent. Multi-host deployment requires a shared
transactional limiter; do not place SQLite on a network filesystem.

Structured `climate_platform.audit` events cover authenticated API requests and
denials, including administrator metadata reads, identity, key ID, method, status,
UTC timestamp and bytes received. No credentials or request body are logged.
Collect stdout into restricted, durable central logging with an explicit retention
policy; local container logs alone are not a tamper-proof audit archive.

## TLS

Collector config enforces HTTPS except literal loopback IPs and localhost, even
when Config is constructed directly. TLS certificate validation stays enabled;
redirects are not followed. Configure a real hostname and certificate in
`deploy/nginx.conf`, install it on the host, validate with `nginx -t`, and start
with `docker compose up -d` after setting the authentication variables above.
Only Nginx exposes public 443; API and MinIO remain loopback-bound. The example
also limits unauthenticated traffic by source IP and caps upload body size.
Test from a remote client using `https://your-host/readyz`, then an authenticated
upload. Do not send credentials to port 80 or trust arbitrary forwarded headers.

## Images, scan and SBOM

Compose runs this project's own source-built MinIO images:
`noname12346767/my-minio` (server) and `noname12346767/mc-allos` (client). Set
`MINIO_IMAGE=<repo>@sha256:...` and `MINIO_MC_IMAGE=<repo>@sha256:...` to the exact
digest-pinned references you built and published, so the release gate verifies the
same image the deployment runs. Do not substitute an upstream publisher's image
(`quay.io/minio/*`, `minio/*`); that is a different product and is not what this
project ships. The gate fails closed when a reference is missing or is not pinned
to a `sha256:` digest.

Run
`python scripts/release/verify_images.py --api-image <tested-api-image> --worker-image <tested-worker-image>`
with Docker and Trivy installed. It resolves the exact `MINIO_IMAGE`/`MINIO_MC_IMAGE`
references (local image first, otherwise that pinned pull), writes CycloneDX SBOMs and
JSON vulnerability reports, and fails on HIGH/CRITICAL findings. Retain
`security-artifacts/` with release evidence. Run the same gate locally before the
Compose smoke; this project has no CI/CD pipeline. Registry origin plus digest is not a
publisher cryptographic signature; do not claim signed provenance without a verified
publisher attestation.

The gate only verifies the images it is given, so Compose must resolve the same
references. Compose reads `MINIO_IMAGE`/`MINIO_MC_IMAGE`; when both are set to the
pinned references above, the images that run and the images the gate scans are
identical. The default tags exist for local development only and do not pass the gate.
Existing running containers/data volumes are not modified by these code changes.

## Optional audit storage controls

Provision an external KMS and MinIO KMS connectivity, then configure Bronze default
SSE-KMS using `mc encrypt set sse-kms <key-id> lake/<bronze-bucket>`.
Set `REQUIRE_SSE_KMS=True` to fail startup unless bucket defaults use aws:kms.
KMS availability and existing-object encryption need separate operational checks;
enabling a bucket default does not retroactively encrypt historical versions.

Object Lock requires a reviewed retention duration/mode and bucket capability.
For a new audit bucket, create it with `mc mb --with-lock`, enable a reviewed
default retention with `mc retention set --default GOVERNANCE <duration>`, and
set `REQUIRE_OBJECT_LOCK=True`. Startup checks enabled lock and default retention.
Do not automatically apply irreversible compliance retention to existing raw data.
These flags verify provisioned controls; they do not provision KMS or migrate data.
Reference: https://min.io/docs/minio/linux/administration/server-side-encryption/server-side-encryption-sse-kms.html
and https://min.io/docs/minio/linux/administration/object-management/object-retention.html.

## Stage 2 registry lifecycle

Registry schema creation/migration runs explicitly during startup, outside the
request path. Normal connections open an existing database (mode=rw), set local
PRAGMAs and do not acquire a schema writer lock. S3 network I/O runs outside
transactions; short optimistic commit transactions re-check ownership/hash/revision.
Busy/locked registry operations return 503 with Retry-After: 1 and a configurable
SQLITE_BUSY_TIMEOUT_SECONDS (default 0.5, maximum 5). This is not a total request
deadline. Readiness still probes write availability and can briefly report 503
during genuine contention; its cache/timeout behavior is unchanged.

Stage 5 also scans the exact locally built API/worker image IDs and emits their SBOMs.
See [checkpoint and local release validation gates](STAGE5_PRODUCTION_READINESS.md). A successful
scan manifest is removed before a new run, so a failed scan cannot leave a stale PASS.
