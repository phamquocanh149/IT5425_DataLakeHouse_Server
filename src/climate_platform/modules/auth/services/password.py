"""Password hashing/verification (PBKDF2-SHA256) for Portal user accounts.

Implementation lives in ``common.security`` so the auth service and the credentials
repository share one copy; this module re-exports it for the auth module surface.
"""

from climate_platform.common.security import (
    PBKDF2_ITERATIONS,
    hash_password,
    verify_password,
)

__all__ = ["PBKDF2_ITERATIONS", "hash_password", "verify_password"]
