"""USDM product publication and verification.

One job: publish the immutable layer products through the shared medallion publisher
(atomic, never overwrite a different payload) and verify a published artifact set. Fixes the
old bypass where this logic was re-implemented inline.
"""

from __future__ import annotations


from climate_platform.medallion.io import file_hash
from climate_platform.medallion.publisher import product_path, publish_atomic

PRODUCTS = (
    ("silver", "silver.parquet"),
    ("gold", "gold.csv"),
    ("quality", "quality.json"),
    ("reference", "grid.csv"),
)


def publish_products(root, stage, grid, build, day):
    """Copy each produced artifact to its immutable product path; return the manifest entries."""
    products = {}
    for layer, name in PRODUCTS:
        path = grid if layer == "reference" else stage / name
        digest = file_hash(path)
        relative = product_path(layer, "usdm", day, build, digest, path.suffix)
        publish_atomic(path, root / relative, digest)
        products[layer] = {"path": relative.as_posix(), "sha256": digest}
    return products


def verify_products(root, manifest):
    resolved_root = root.resolve()
    for product in manifest["products"].values():
        path = root / product["path"]
        if not path.resolve().is_relative_to(resolved_root):
            raise ValueError("Published product escapes the release root")
        if not path.is_file() or file_hash(path) != product["sha256"]:
            raise ValueError("Published product requires reconciliation")
