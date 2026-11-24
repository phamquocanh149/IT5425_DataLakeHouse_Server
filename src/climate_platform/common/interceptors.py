"""Interceptor helpers (request-id, security headers, timing).

FastAPI has no native interceptor concept, so request-scoped cross-cutting work is
expressed with middleware and dependencies. Helpers that more than one module needs
belong here.
"""
