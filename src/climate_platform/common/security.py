"""Shared password hashing (PBKDF2-SHA256) for Portal user accounts.

Lives in ``common`` so the auth service and the credentials repository share one copy
without the data layer importing a feature module.
"""

import base64
import hashlib
import secrets

PBKDF2_ITERATIONS = 200_000


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password, stored):
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(iterations)
        )
        return secrets.compare_digest(computed, base64.b64decode(digest))
    except (AttributeError, ValueError, TypeError):
        return False
