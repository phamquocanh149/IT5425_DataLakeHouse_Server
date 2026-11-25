"""Unit tests for the S3 layer store (fake client, no network)."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

import pytest
from botocore.exceptions import ClientError

from climate_platform.s3.layers import LayerStore


class Body:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@dataclass
class Stored:
    data: bytes
    etag: str
    checksum: str | None


def _stored(data: bytes, checksum=True):
    digest = hashlib.sha256(data).hexdigest()
    return Stored(
        data=data,
        etag=f'"{digest}"',
        checksum=base64.b64encode(bytes.fromhex(digest)).decode("ascii") if checksum else None,
    )


def _missing(operation):
    raise ClientError({"Error": {"Code": "NoSuchKey"}}, operation)


class FakeClient:
    def __init__(self, *, echo_checksum=True, store_checksum=True):
        self.objects = {}
        self.puts = 0
        self.gets = 0
        self.heads = 0
        self.put_hook = None
        self.echo_checksum = echo_checksum
        self.store_checksum = store_checksum

    def seed(self, Key, data):
        self.objects[Key] = _stored(data)

    def get_object(self, Bucket, Key):
        self.gets += 1
        item = self.objects.get(Key)
        if item is None:
            _missing("GetObject")
        return {"Body": Body(item.data), "ContentLength": len(item.data), "ETag": item.etag}

    def head_object(self, Bucket, Key, ChecksumMode=None):
        self.heads += 1
        item = self.objects.get(Key)
        if item is None:
            _missing("HeadObject")
        result = {"ContentLength": len(item.data), "ETag": item.etag}
        if item.checksum is not None:
            result["ChecksumSHA256"] = item.checksum
        return result

    def put_object(
        self,
        Bucket,
        Key,
        Body,
        ContentLength,
        ContentType,
        ChecksumSHA256=None,
        Metadata=None,
        IfMatch=None,
        IfNoneMatch=None,
        **kwargs,
    ):
        if self.put_hook is not None:
            hook, self.put_hook = self.put_hook, None
            hook(self, Key)
        item = self.objects.get(Key)
        if IfNoneMatch == "*" and item is not None:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        if IfMatch is not None and (item is None or item.etag != IfMatch):
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        data = Body.read()
        assert len(data) == ContentLength
        stored = _stored(data, checksum=self.store_checksum)
        self.objects[Key] = stored
        self.puts += 1
        response = {"ETag": stored.etag}
        if self.echo_checksum and ChecksumSHA256:
            response["ChecksumSHA256"] = ChecksumSHA256
        return response


def test_publish_uploads_once_then_skips_identical(tmp_path):
    store = LayerStore("climate-silver", client=FakeClient())
    path = tmp_path / "data.parquet"
    path.write_bytes(b"payload")

    first = store.publish(path, "nldas/FORA/year=2021/data.parquet")
    second = store.publish(path, "nldas/FORA/year=2021/data.parquet")

    assert first["uploaded"] is True
    assert second["uploaded"] is False
    assert store.client.puts == 1
    assert store.client.gets == 0
    assert store.client.objects["nldas/FORA/year=2021/data.parquet"].data == b"payload"


def test_publish_updates_changed_payload(tmp_path):
    store = LayerStore("climate-silver", client=FakeClient())
    path = tmp_path / "data.parquet"
    path.write_bytes(b"old")
    store.publish(path, "key")
    path.write_bytes(b"new")

    assert store.publish(path, "key")["uploaded"] is True
    assert store.client.objects["key"].data == b"new"


def test_publish_survives_concurrent_identical_writer(tmp_path):
    client = FakeClient()
    store = LayerStore("climate-silver", client=client)
    path = tmp_path / "data.parquet"
    path.write_bytes(b"payload")
    client.seed("key", b"payload")

    result = store.publish(path, "key")

    assert result["uploaded"] is False
    assert client.puts == 0


def test_publish_retries_after_concurrent_create(tmp_path):
    client = FakeClient()
    store = LayerStore("climate-silver", client=client)
    path = tmp_path / "data.parquet"
    path.write_bytes(b"local")

    def race(racing, Key):
        racing.objects[Key] = _stored(b"other")

    client.put_hook = race
    result = store.publish(path, "key")

    assert result["uploaded"] is True
    assert client.puts == 1
    assert client.objects["key"].data == b"local"


def test_publish_retries_when_etag_changes_between_read_and_write(tmp_path):
    client = FakeClient()
    store = LayerStore("climate-silver", client=client)
    path = tmp_path / "data.parquet"
    path.write_bytes(b"local")
    client.seed("key", b"old")

    def race(racing, Key):
        racing.objects[Key] = _stored(b"racer")

    client.put_hook = race
    result = store.publish(path, "key")

    assert result["uploaded"] is True
    assert client.objects["key"].data == b"local"
    assert client.puts == 1


def test_publish_falls_back_to_get_when_server_has_no_checksum(tmp_path):
    client = FakeClient(echo_checksum=False, store_checksum=False)
    store = LayerStore("climate-silver", client=client)
    path = tmp_path / "data.parquet"
    path.write_bytes(b"payload")

    assert store.publish(path, "key")["uploaded"] is True
    assert client.gets >= 1
    assert client.objects["key"].data == b"payload"


def test_publish_rejects_server_checksum_mismatch(tmp_path):
    client = FakeClient(echo_checksum=False)
    store = LayerStore("climate-silver", client=client)
    path = tmp_path / "data.parquet"
    path.write_bytes(b"payload")
    original = client.put_object

    def corrupt(*args, **kwargs):
        response = original(*args, **kwargs)
        client.objects["key"] = _stored(b"corrupt")
        return response

    client.put_object = corrupt
    with pytest.raises(ValueError):
        store.publish(path, "key")


def test_download_verifies_checksum_and_size(tmp_path):
    client = FakeClient()
    data = b"bronze-object"
    client.seed("raw.nc", data)
    store = LayerStore("climate-bronze", client=client)
    target = tmp_path / "out" / "raw.nc"

    store.download(
        "raw.nc",
        target,
        expected_size=len(data),
        expected_sha256=hashlib.sha256(data).hexdigest(),
    )
    assert target.read_bytes() == data
    assert not target.with_name(target.name + ".part").exists()


def test_download_rejects_bad_checksum(tmp_path):
    client = FakeClient()
    client.seed("raw.nc", b"data")
    store = LayerStore("climate-bronze", client=client)
    target = tmp_path / "raw.nc"

    with pytest.raises(ValueError):
        store.download("raw.nc", target, expected_sha256="0" * 64)
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()
