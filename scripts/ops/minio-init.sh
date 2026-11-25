#!/bin/sh
set -eu
export MC_CONFIG_DIR=/tmp/mc
require() {
  if [ -z "${1:-}" ]; then
    echo "Missing required environment variable: $2" >&2
    exit 1
  fi
}
require "$MINIO_ROOT_USER" MINIO_ROOT_USER
require "$MINIO_ROOT_PASSWORD" MINIO_ROOT_PASSWORD
require "$S3_ACCESS_KEY" S3_ACCESS_KEY
require "$S3_SECRET_KEY" S3_SECRET_KEY
require "$MEDALLION_S3_ACCESS_KEY" MEDALLION_S3_ACCESS_KEY
require "$MEDALLION_S3_SECRET_KEY" MEDALLION_S3_SECRET_KEY
test "$S3_ACCESS_KEY" != "$MINIO_ROOT_USER"
test "$MEDALLION_S3_ACCESS_KEY" != "$MINIO_ROOT_USER"
test "$MEDALLION_S3_ACCESS_KEY" != "$S3_ACCESS_KEY"
if [ "$MEDALLION_S3_SECRET_KEY" = "$MINIO_ROOT_PASSWORD" ]; then
  echo 'MEDALLION_S3_SECRET_KEY must differ from MINIO_ROOT_PASSWORD; set a dedicated medallion secret' >&2
  exit 1
fi
# Names are embedded into policy JSON; restrict them before interpolation.
for bucket in "$S3_BUCKET_BRONZE" "$S3_BUCKET_SILVER" "$S3_BUCKET_GOLD" "$S3_BUCKET_WAREHOUSE"; do
  case "$bucket" in ''|*[!a-z0-9-]*) echo 'Invalid bucket name' >&2; exit 1;; esac
  test "${#bucket}" -ge 3 && test "${#bucket}" -le 63
done
case "$MEDALLION_S3_ACCESS_KEY" in ''|*[!A-Za-z0-9_-]*) echo 'Invalid medallion access key' >&2; exit 1;; esac
test "${#MEDALLION_S3_ACCESS_KEY}" -ge 3 && test "${#MEDALLION_S3_ACCESS_KEY}" -le 20
if [ "${#MEDALLION_S3_SECRET_KEY}" -lt 8 ] || [ "${#MEDALLION_S3_SECRET_KEY}" -gt 40 ]; then
  echo 'MEDALLION_S3_SECRET_KEY must be 8-40 characters; do not reuse MINIO_ROOT_PASSWORD' >&2
  exit 1
fi
mc alias set lake http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc ready lake
for bucket in "$S3_BUCKET_BRONZE" "$S3_BUCKET_SILVER" "$S3_BUCKET_GOLD" "$S3_BUCKET_WAREHOUSE"; do
  mc mb --ignore-existing "lake/$bucket"
  mc anonymous set none "lake/$bucket"
  mc version enable "lake/$bucket"
done
cat > /tmp/bronze-policy.json <<EOF
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket","s3:GetBucketVersioning","s3:GetBucketPolicy","s3:GetEncryptionConfiguration","s3:GetBucketObjectLockConfiguration"],"Resource":["arn:aws:s3:::$S3_BUCKET_BRONZE"]},
 {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject"],"Resource":["arn:aws:s3:::$S3_BUCKET_BRONZE/source=usdm/*","arn:aws:s3:::$S3_BUCKET_BRONZE/source=noaa/*","arn:aws:s3:::$S3_BUCKET_BRONZE/source=usgs/*","arn:aws:s3:::$S3_BUCKET_BRONZE/source=nldas/*"]}
]}
EOF
cat > /tmp/medallion-policy.json <<EOF
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket"],"Resource":["arn:aws:s3:::$S3_BUCKET_BRONZE"]},
 {"Effect":"Allow","Action":["s3:GetObject"],"Resource":["arn:aws:s3:::$S3_BUCKET_BRONZE/source=*/*"]},
 {"Effect":"Allow","Action":["s3:PutObject"],"Resource":["arn:aws:s3:::$S3_BUCKET_BRONZE/source=usdm/*"]},
 {"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket"],"Resource":["arn:aws:s3:::$S3_BUCKET_SILVER","arn:aws:s3:::$S3_BUCKET_GOLD"]},
 {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject"],"Resource":["arn:aws:s3:::$S3_BUCKET_SILVER/*","arn:aws:s3:::$S3_BUCKET_GOLD/*"]}
]}
EOF
# Reconcile users and policies so a credential or bucket-name change takes effect.
for user in "$S3_ACCESS_KEY" "$MEDALLION_S3_ACCESS_KEY"; do
  if mc admin user info lake "$user" >/dev/null 2>&1; then
    mc admin user rm lake "$user" >/dev/null
  fi
done
for policy in climate-bronze-ingestion climate-medallion-publish-v2; do
  if mc admin policy info lake "$policy" >/dev/null 2>&1; then
    mc admin policy rm lake "$policy" >/dev/null
  fi
done
mc admin policy create lake climate-bronze-ingestion /tmp/bronze-policy.json
mc admin policy create lake climate-medallion-publish-v2 /tmp/medallion-policy.json
mc admin user add lake "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null
mc admin user add lake "$MEDALLION_S3_ACCESS_KEY" "$MEDALLION_S3_SECRET_KEY" >/dev/null
mc admin policy attach lake climate-bronze-ingestion --user "$S3_ACCESS_KEY"
mc admin policy attach lake climate-medallion-publish-v2 --user "$MEDALLION_S3_ACCESS_KEY"
echo 'Four private versioned buckets, Bronze ingestion and medallion publish identities ready'
