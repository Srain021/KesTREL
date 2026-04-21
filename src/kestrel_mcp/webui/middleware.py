"""ASGI middleware for binding a RequestContext to every HTTP request."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core import ServiceContainer


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Open a fresh context for each request.

    The first skeleton has no active engagement by default. Later Web UI RFCs
    can resolve an engagement from a header, cookie, or route parameter.
    """

    def __init__(self, app: ASGIApp, container: ServiceContainer) -> None:
        super().__init__(app)
        self.container = container

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        async with self.container.open_context() as ctx:
            request.state.ctx = ctx
            return await call_next(request)


__all__ = ["RequestContextMiddleware"]
