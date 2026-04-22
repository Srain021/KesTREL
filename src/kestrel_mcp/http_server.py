"""HTTP transport for reverse-proxied MCP access.

The normal ``serve`` command stays stdio-first for local MCP hosts. This
module exposes the same low-level MCP server over Streamable HTTP so a team can
put Caddy/Nginx/Tailscale in front of it without losing the local direct path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Settings, load_settings
from .core import ServiceContainer
from .logging import configure_logging
from .server import RedTeamMCPServer


class BearerTokenASGIApp:
    """Require a static Bearer token before handing traffic to MCP transport."""

    def __init__(self, app: ASGIApp, token: str | None) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.token:
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode("latin1")
            expected = f"Bearer {self.token}"
            if not _constant_time_equal(auth, expected):
                await Response(
                    "Unauthorized",
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
                return
        await self.app(scope, receive, send)


class StreamableHTTPASGIApp:
    """ASGI adapter around the MCP SDK's session manager."""

    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self.session_manager = session_manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.session_manager.handle_request(scope, receive, send)


def create_http_app(
    settings: Settings | None = None,
    *,
    container: ServiceContainer | None = None,
    token: str | None = None,
    endpoint: str = "/mcp",
    json_response: bool = False,
    stateless: bool = False,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    enable_dns_rebinding_protection: bool = False,
) -> Starlette:
    """Build an ASGI app exposing MCP over Streamable HTTP."""

    settings = settings or load_settings()
    owns_container = container is None
    container = container or ServiceContainer.default_on_disk(
        credential_encryption_required=settings.features.credential_encryption_required,
    )
    mcp = RedTeamMCPServer(settings, container=container).build()
    security_settings = TransportSecuritySettings(
        enable_dns_rebinding_protection=enable_dns_rebinding_protection,
        allowed_hosts=allowed_hosts or [],
        allowed_origins=allowed_origins or [],
    )
    session_manager = StreamableHTTPSessionManager(
        app=mcp,
        json_response=json_response,
        stateless=stateless,
        security_settings=security_settings,
        session_idle_timeout=None if stateless else 1800,
    )

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        if owns_container:
            await container.initialise()
        async with session_manager.run():
            try:
                yield
            finally:
                if owns_container:
                    await container.dispose()

    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "ok": True,
                "transport": "streamable-http",
                "endpoint": endpoint,
                "edition": settings.edition,
            }
        )

    mcp_app = BearerTokenASGIApp(StreamableHTTPASGIApp(session_manager), token=token)
    return Starlette(
        routes=[
            Route("/__healthz", healthz, methods=["GET"]),
            Route(endpoint, endpoint=mcp_app, methods=["GET", "POST", "DELETE"]),
        ],
        lifespan=lifespan,
    )


def run_http_sync(
    settings: Settings | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    endpoint: str = "/mcp",
    token: str | None = None,
    json_response: bool = False,
    stateless: bool = False,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    enable_dns_rebinding_protection: bool = False,
) -> None:
    """Blocking HTTP server entry point used by the CLI."""

    settings = settings or load_settings()
    configure_logging(
        level=settings.logging.level,
        log_dir=settings.expanded_path(settings.logging.dir) if settings.logging.dir else None,
        json_mode=settings.logging.format == "json",
    )
    app = create_http_app(
        settings,
        token=token,
        endpoint=endpoint,
        json_response=json_response,
        stateless=stateless,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
        enable_dns_rebinding_protection=enable_dns_rebinding_protection,
    )
    uvicorn.run(app, host=host, port=port, log_level=settings.logging.level.lower())


def _constant_time_equal(left: str, right: str) -> bool:
    # Local import keeps startup light for the common stdio-only path.
    import secrets

    return secrets.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


__all__ = ["create_http_app", "run_http_sync"]
