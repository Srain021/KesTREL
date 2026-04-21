"""FastAPI application factory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse

from ..core import RequestContext, ServiceContainer
from .deps import get_ctx
from .middleware import RequestContextMiddleware
from .templating import templates


def create_app(container: ServiceContainer) -> FastAPI:
    """Build the Web UI app around a shared :class:`ServiceContainer`."""

    app = FastAPI(
        title="kestrel-mcp web",
        version="0.1.0",
        docs_url="/__docs",
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware, container=container)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def root(
        request: Request,
        ctx: Annotated[RequestContext, Depends(get_ctx)],
    ) -> HTMLResponse:
        engagements = await ctx.engagement.list()
        return templates.TemplateResponse(
            request,
            "dashboard.html.j2",
            {
                "engagement_count": len(engagements),
                "active_engagement": None,
                "now": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
        )

    @app.get("/__healthz", include_in_schema=False)
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

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
