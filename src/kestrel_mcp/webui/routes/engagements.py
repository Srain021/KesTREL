from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ...core import RequestContext
from ...domain import entities as ent
from ...domain.errors import EngagementNotFoundError, UniqueConstraintError
from ..deps import get_ctx
from ..templating import templates

router = APIRouter()


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def list_engagements(
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
) -> HTMLResponse:
    engagements = await ctx.engagement.list()
    return templates.TemplateResponse(
        request,
        "engagements/list.html.j2",
        {"engagements": engagements, "active_engagement": None},
    )


@router.post("", response_class=HTMLResponse)
@router.post("/", response_class=HTMLResponse)
async def create_engagement(
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
    name: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    client: Annotated[str, Form()],
    engagement_type: Annotated[str, Form()] = "ctf",
) -> HTMLResponse:
    try:
        engagement = await ctx.engagement.create(
            name=name,
            display_name=display_name,
            engagement_type=ent.EngagementType(engagement_type),
            client=client,
        )
    except UniqueConstraintError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc

    return templates.TemplateResponse(
        request,
        "engagements/_form.html.j2",
        {"engagement": engagement, "append_row": True},
    )


@router.get("/{slug}", response_class=HTMLResponse)
async def show_engagement(
    slug: str,
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
) -> HTMLResponse:
    try:
        engagement = await ctx.engagement.get_by_name(slug)
    except EngagementNotFoundError as exc:
        raise HTTPException(404, f"Engagement '{slug}' not found") from exc

    scope = await ctx.scope.list_entries(engagement.id)
    findings = await ctx.finding.list_for_engagement(engagement.id)
    targets = await ctx.target.list_for_engagement(engagement.id)
    return templates.TemplateResponse(
        request,
        "engagements/show.html.j2",
        {
            "engagement": engagement,
            "scope": scope,
            "findings": findings,
            "targets": targets,
            "active_engagement": engagement,
        },
    )
