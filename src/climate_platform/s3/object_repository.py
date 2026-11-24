"""Object-storage repository contract.

A single repository interface fronts every object-storage backend (MinIO/S3, local
filesystem Bronze). Catalog and processing depend on this protocol, not on a driver.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectRepository(Protocol):
    bucket: str

    def publish(self, path, key, sha256, size): ...

    def verify(self, key, sha256, size, bucket=None): ...

    def get_object(self, **kwargs): ...

    def objects(self): ...
