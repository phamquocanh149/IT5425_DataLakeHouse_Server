import hashlib

import pytest

from climate_platform.infrastructure.object_store import object_key


def test_partition_keys_preserve_scientific_identity_safely():
    sha = hashlib.sha256(b"raw").hexdigest()
    key = object_key("usdm", "2021-06-22", "../../station/đặc biệt", 2, sha, "raw.zip")
    assert key.startswith("source=usdm/year=2021/date=2021-06-22/dataset=")
    assert key.endswith(f"/revision=2/sha256={sha}/raw.zip")
    assert ".." not in key and "đ" not in key
    assert key != object_key("usdm", "2021-06-22", "station", 2, sha, "raw.zip")
    assert key != object_key("usdm", "2021-06-22", "../../station/đặc biệt", 1, sha, "raw.zip")


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "../bad"},
        {"source_date": "2021-02-30"},
        {"revision": 0},
        {"sha256": "../hash"},
        {"dataset_key": "\x00"},
        {"dataset_key": " "},
    ],
)
def test_invalid_object_identity_rejected(changes):
    values = dict(
        source="usdm",
        source_date="2021-06-22",
        dataset_key="station",
        revision=1,
        sha256="a" * 64,
        filename="raw.csv",
    )
    values.update(changes)
    with pytest.raises(ValueError):
        object_key(**values)
