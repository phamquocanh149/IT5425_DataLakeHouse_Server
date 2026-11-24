"""Portal request admission: demo loopback, session, CSRF/body cap, rate limit, lease.

One job: decide whether a Portal request may proceed and acquire its preview lease. No
response headers, no error formatting, no request-id generation — the middleware composes
these helpers and owns the transport concerns.
"""

import secrets

from starlette.concurrency import run_in_threadpool

from climate_platform.modules.portal.errors import PortalError

PREFIX = "/api/portal/v1"
# Logout is public on purpose: it must stay idempotent so a client whose session already
# expired can still clear the cookie (no 401 blocking the browser from logging out).
PUBLIC_PATHS = {PREFIX + "/auth/login", PREFIX + "/auth/info", PREFIX + "/auth/logout"}

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "testclient"}
LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "testserver"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUEST_BODY_LIMIT = 16384


def enforce_demo_loopback(config, request):
    """Explicit demo only; forwarded headers cannot elevate remote callers."""
    if not config.demo:
        return
    if request.client and request.client.host not in LOOPBACK_HOSTS:
        raise PortalError(403, "LOOPBACK_DEMO_ONLY")
    if request.url.hostname not in LOCAL_HOSTNAMES:
        raise PortalError(403, "LOOPBACK_DEMO_ONLY")


def category_for(path):
    return "preview" if path.endswith(("/preview", "/map")) else "metadata"


async def cap_body(request):
    """Buffer a write body, rejecting an oversized one before routing.

    Applied to public writes too (login): without it an unauthenticated client could force
    an unbounded read/allocation before the DTO's field bounds are ever evaluated.
    """
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > REQUEST_BODY_LIMIT):
        raise PortalError(413, "REQUEST_TOO_LARGE")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > REQUEST_BODY_LIMIT:
            raise PortalError(413, "REQUEST_TOO_LARGE")
    request._body = bytes(body)


async def enforce_csrf_and_cap(request, user, origin):
    """Reject cross-site writes and cap the buffered write body before routing."""
    if request.method not in WRITE_METHODS:
        return
    if request.headers.get("origin") != origin.rstrip("/") or not secrets.compare_digest(
        request.headers.get("x-csrf-token", ""), user["csrf"]
    ):
        raise PortalError(403, "CSRF_FAILED")
    await cap_body(request)


async def admit(store, request, config, path):
    """Return ``(actor, lease)`` once the request is authenticated and within limits."""
    if path in PUBLIC_PATHS:
        host = request.client.host if request.client else "unknown"
        await run_in_threadpool(store.limit, "auth:" + host, "metadata")
        if request.method in WRITE_METHODS:
            await cap_body(request)
        return None, None
    user = await run_in_threadpool(store.session, request.cookies.get("portal_session"), config)
    request.state.portal_user = user
    actor = user["user_id"]
    await enforce_csrf_and_cap(request, user, config.origin)
    category = category_for(path)
    await run_in_threadpool(store.limit, actor, category)
    lease = None
    if category == "preview":
        lease = await run_in_threadpool(store.acquire, actor, "preview", 4, 10)
    return actor, lease
