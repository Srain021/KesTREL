from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ...core import RequestContext
from ...domain import entities as ent
from ...domain.errors import EngagementNotFoundError, InvalidStateTransitionError
from ..deps import get_ctx
from ..templating import templates

router = APIRouter()


async def _get_engagement_or_404(ctx: RequestContext, slug: str) -> ent.Engagement:
    try:
        return await ctx.engagement.get_by_name(slug)
    except EngagementNotFoundError as exc:
        raise HTTPException(404, f"Engagement '{slug}' not found") from exc


def _parse_severity(value: str | None) -> ent.FindingSeverity | None:
    if not value:
        return None
    try:
        return ent.FindingSeverity(value)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid severity '{value}'") from exc


def _parse_status(value: str | None) -> ent.FindingStatus | None:
    if not value:
        return None
    try:
        return ent.FindingStatus(value)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid status '{value}'") from exc


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def list_findings(
    slug: str,
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
    severity: str | None = None,
    status: str | None = None,
) -> HTMLResponse:
    engagement = await _get_engagement_or_404(ctx, slug)
    severity_filter = _parse_severity(severity)
    status_filter = _parse_status(status)
    findings = await ctx.finding.list_for_engagement(
        engagement.id,
        severity=severity_filter,
        status=status_filter,
    )
    return templates.TemplateResponse(
        request,
        "findings/table.html.j2",
        {
            "active_engagement": engagement,
            "engagement": engagement,
            "findings": findings,
            "severities": list(ent.FindingSeverity),
            "statuses": list(ent.FindingStatus),
            "selected_severity": severity,
            "selected_status": status,
            "slug": slug,
        },
    )


@router.post("/{finding_id}/transition", response_class=HTMLResponse)
async def transition_finding(
    slug: str,
    finding_id: UUID,
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
    status: Annotated[str, Form()],
    note: Annotated[str, Form()] = "",
) -> HTMLResponse:
    engagement = await _get_engagement_or_404(ctx, slug)
    current = await ctx.finding.get(finding_id)
    if current is None or current.engagement_id != engagement.id:
        raise HTTPException(404, f"Finding '{finding_id}' not found")

    parsed_status = _parse_status(status)
    if parsed_status is None:
        raise HTTPException(400, "Missing status")

    try:
        finding = await ctx.finding.transition(finding_id, parsed_status, note=note)
    except InvalidStateTransitionError as exc:
        raise HTTPException(409, str(exc)) from exc

    return templates.TemplateResponse(
        request,
        "findings/_row.html.j2",
        {
            "f": finding,
            "slug": slug,
            "statuses": list(ent.FindingStatus),
        },
    )
