"""Processing-layer publication helpers (re-exported from the medallion standard).

The single implementation now lives in ``medallion.publisher``; this module only keeps the
historical ``modules.processing.publisher`` import path working.
"""

from climate_platform.medallion.publisher import file_hash, product_path, publish_atomic

__all__ = ["file_hash", "publish_atomic", "product_path"]
