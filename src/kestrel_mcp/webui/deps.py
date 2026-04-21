"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Request

from ..core import RequestContext


def get_ctx(request: Request) -> RequestContext:
    """Return the request-bound :class:`RequestContext`."""

    ctx = getattr(request.state, "ctx", None)
    if ctx is None:
        raise RuntimeError("RequestContextMiddleware must be installed before routes run.")
    if not isinstance(ctx, RequestContext):
        raise RuntimeError("request.state.ctx is not a RequestContext.")
    return ctx


__all__ = ["get_ctx"]
