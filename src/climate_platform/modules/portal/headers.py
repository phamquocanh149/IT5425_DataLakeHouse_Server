"""Portal response security headers.

One job: apply the fixed security header set (request id, MIME sniffing, referrer, cache
and CSP) to an outgoing response.
"""

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def apply_security_headers(response, request_id):
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Security-Policy"] = CSP
    return response
