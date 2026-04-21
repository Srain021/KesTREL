"""FastAPI application factory."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI

from ..core import RequestContext, ServiceContainer
from .deps import get_ctx
from .middleware import RequestContextMiddleware


def create_app(container: ServiceContainer) -> FastAPI:
    """Build the Web UI app around a shared :class:`ServiceContainer`."""

    app = FastAPI(
        title="kestrel-mcp web",
        version="0.1.0",
        docs_url="/__docs",
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware, container=container)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, object]:
        return {"ok": True, "service": "kestrel-mcp web"}

    @app.get("/api/v1/engagements")
    async def list_engagements(
        ctx: Annotated[RequestContext, Depends(get_ctx)],
    ) -> dict[str, object]:
        engagements = await ctx.engagement.list()
        return {
            "count": len(engagements),
            "engagements": [
                {
                    "id": str(engagement.id),
                    "name": engagement.name,
                    "status": engagement.status.value,
                }
                for engagement in engagements
            ],
        }

    return app


__all__ = ["create_app"]
