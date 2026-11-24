"""Reusable pipes (input validation/transformation) shared across modules.

Upload-specific pipes live in ``climate_platform.modules.ingestion.validation``; this
module is the home for validation helpers that end up needed by more than one module.

``RequestContext`` is the HTTP-free view of a request that controllers hand to services:
services own business logic but must not import FastAPI/Starlette request objects.
"""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RequestContext:
    """Everything a service may need from a request, without any HTTP dependency."""

    request_id: str
    path: str
    params: Mapping[str, str]
    pairs: tuple[tuple[str, str], ...]
    headers: Mapping[str, str]


def request_ctx(request) -> RequestContext:
    """Build a :class:`RequestContext` from a Starlette/FastAPI request."""
    return RequestContext(
        request_id=request.state.request_id,
        path=request.url.path,
        params=dict(request.query_params),
        pairs=tuple(request.query_params.multi_items()),
        headers={k.lower(): v for k, v in request.headers.items()},
    )
