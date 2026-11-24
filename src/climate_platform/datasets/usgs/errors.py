"""USGS pipeline error types.

One job: the two domain errors the crawl layer raises so callers can distinguish an auth
failure (stop the run) from an API failure (retry/abort).
"""


class AuthError(RuntimeError):
    pass


class APIError(RuntimeError):
    pass
