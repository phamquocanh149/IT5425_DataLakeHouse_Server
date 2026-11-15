#!/bin/sh
set -eu
export MC_CONFIG_DIR=/tmp/mc
test "$S3_ACCESS_KEY" != "$MINIO_ROOT_USER"
# Names are embedded into policy JSON; restrict them before interpolation.
for bucket in "$S3_BUCKET_BRONZE" "$S3_BUCKET_SILVER" "$S3_BUCKET_GOLD" "$S3_BUCKET_WAREHOUSE"; do
  case "$bucket" in ''|*[!a-z0-9-]*) echo 'Invalid bucket name' >&2; exit 1;; esac
  test "${#bucket}" -ge 3 && test "${#bucket}" -le 63
done
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
# Dedicated non-root ingestion identity; no delete, admin, or Silver/Gold/Warehouse access.
mc admin user add lake "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null
mc admin policy create lake climate-bronze-ingestion /tmp/bronze-policy.json
mc admin policy attach lake climate-bronze-ingestion --user "$S3_ACCESS_KEY"
echo 'Four private versioned buckets and Bronze ingestion identity ready'
