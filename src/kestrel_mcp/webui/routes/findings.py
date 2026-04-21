from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ...analysis import assess_exploitability
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


def _readiness_by_id(findings: list[ent.Finding]) -> dict[str, dict[str, object]]:
    return {str(f.id): _readiness_card(f) for f in findings}


def _readiness_card(finding: ent.Finding) -> dict[str, object]:
    assessment = assess_exploitability(finding)
    first_gap = assessment.evidence_gaps[0] if assessment.evidence_gaps else ""
    first_step = assessment.recommended_next_steps[0] if assessment.recommended_next_steps else ""
    return {
        "score": assessment.score,
        "rating": assessment.rating.value,
        "confidence": assessment.confidence,
        "requires_human_approval": assessment.requires_human_approval,
        "first_gap": first_gap,
        "first_step": first_step,
    }


def _risk_for_rating(rating: str) -> str:
    return {
        "operator_review": "critical",
        "ready_to_validate": "high",
        "investigate": "medium",
        "parked": "low",
    }.get(rating, "medium")


def _fire_control_packet(
    *,
    engagement: ent.Engagement,
    finding: ent.Finding,
    target: ent.Target | None,
) -> dict[str, object]:
    assessment = assess_exploitability(finding)
    target_label = target.value if target else str(finding.target_id)
    evidence_gaps = list(assessment.evidence_gaps)
    return {
        "approved": False,
        "approval_required": True,
        "next_state": "wait_for_human_approval",
        "engagement_name": engagement.name,
        "finding_title": finding.title,
        "target": target_label,
        "proposed_action": f"Scoped validation for finding: {finding.title}",
        "risk_level": _risk_for_rating(assessment.rating.value),
        "readiness_score": assessment.score,
        "readiness_rating": assessment.rating.value,
        "rationale": (
            "Readiness assessment recommends human review before any active validation "
            "or offensive tool use."
        ),
        "evidence_refs": [f"finding://{engagement.id}/{finding.id}"],
        "evidence_gaps": evidence_gaps,
        "checklist": [
            "Scope and rules of engagement confirmed by a human.",
            "Target and expected validation impact understood.",
            "Evidence gaps reviewed and accepted or closed.",
            "Abort condition and rollback path acknowledged.",
            "Operator explicitly approves any later tool call outside this packet.",
        ],
        "rollback_plan": (
            "Stop validation immediately, preserve current evidence, and do not retry "
            "noisy or destructive actions without a new approval packet."
        ),
    }


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
            "readiness_by_id": _readiness_by_id(findings),
            "severities": list(ent.FindingSeverity),
            "statuses": list(ent.FindingStatus),
            "selected_severity": severity,
            "selected_status": status,
            "slug": slug,
        },
    )


@router.get("/{finding_id}/fire-control", response_class=HTMLResponse)
async def fire_control_packet(
    slug: str,
    finding_id: UUID,
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
) -> HTMLResponse:
    engagement = await _get_engagement_or_404(ctx, slug)
    finding = await ctx.finding.get(finding_id)
    if finding is None or finding.engagement_id != engagement.id:
        raise HTTPException(404, f"Finding '{finding_id}' not found")
    target = await ctx.target.get(finding.target_id)
    packet = _fire_control_packet(engagement=engagement, finding=finding, target=target)
    return templates.TemplateResponse(
        request,
        "findings/_fire_control.html.j2",
        {
            "packet": packet,
            "f": finding,
            "engagement": engagement,
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
            "readiness_by_id": _readiness_by_id([finding]),
            "slug": slug,
            "statuses": list(ent.FindingStatus),
        },
    )
