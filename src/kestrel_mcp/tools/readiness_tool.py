"""Advisory readiness and fire-control tools.

These tools do not execute offensive actions. They package findings and
operator intent into triage, planning, approval, and evidence structures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from ..analysis import CVEEnrichmentClient, assess_exploitability
from ..analysis.readiness import ReadinessAssessment
from ..core.context import current_context_or_none
from ..domain import entities as ent
from .base import ToolModule, ToolResult, ToolSpec


class ReadinessModule(ToolModule):
    id = "readiness"

    def enabled(self) -> bool:
        return True

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="exploitability_triage",
                description=(
                    "Score a finding for operator readiness. Produces prioritization, evidence gaps, "
                    "and human-approval routing; never executes validation or exploit steps."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "description": "Optional active-engagement finding UUID to load.",
                        },
                        "finding": {
                            "type": "object",
                            "description": "Finding-like object when no finding_id is available.",
                        },
                        "enrichment": {
                            "type": "object",
                            "description": "Optional CVE enrichment records keyed by CVE.",
                        },
                        "context": {
                            "type": "object",
                            "description": "Exposure context: service, product, version, auth_required, etc.",
                        },
                        "enrich_cves": {
                            "type": "boolean",
                            "default": False,
                            "description": "If true, perform read-only EPSS/KEV lookup for CVEs.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_triage,
                tags=["analysis", "helper", "audit"],
                when_to_use=[
                    "User asks 'can we attack this', 'how exploitable is this', or 'what should we validate first'.",
                    "Before any high-risk validation, payload generation, or post-exploitation tool.",
                ],
                when_not_to_use=[
                    "User asked to execute an exploit or payload; this tool only advises.",
                    "No finding or finding_id is available; ask for evidence first.",
                ],
                prerequisites=[
                    "Finding metadata from scans, manual notes, or the active engagement DB.",
                    "Optional enrichment can be passed in or fetched read-only with enrich_cves=true.",
                ],
                follow_ups=[
                    "If rating=operator_review, call operator_fire_control before any dangerous tool.",
                    "If evidence gaps exist, collect the missing proof before escalation.",
                    "If no CVE exists but behavior is verified, call zero_day_hypothesis.",
                ],
                pitfalls=[
                    "Score is prioritization, not proof of exploitability.",
                    "Do not treat recommended_next_steps as permission to execute.",
                ],
                local_model_hints=(
                    "This is a brain, not a trigger. Return the assessment and stop before dangerous tools "
                    "unless the human explicitly approves the next action."
                ),
            ),
            ToolSpec(
                name="attack_path_plan",
                description=(
                    "Build an advisory attack-path plan from findings and context. The output is an ordered "
                    "playbook for a human operator, not an execution chain."
                ),
                input_schema={
                    "type": "object",
                    "required": ["findings"],
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Target label or host metadata.",
                        },
                        "findings": {"type": "array", "items": {"type": "object"}, "minItems": 1},
                        "context": {"type": "object"},
                        "max_steps": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_attack_path,
                tags=["analysis", "helper", "audit"],
                when_to_use=[
                    "User wants a route from recon results to validation priorities.",
                    "Multiple findings need ordering into a coherent plan.",
                ],
                pitfalls=[
                    "This does not run tools. It only names suggested tools and approval gates.",
                    "Do not skip scope, ROE, or evidence gates because a plan ranks something first.",
                ],
                local_model_hints="Plan, summarize, and ask for approval. Do not execute the plan.",
            ),
            ToolSpec(
                name="operator_fire_control",
                description=(
                    "Create a human approval packet for a proposed high-risk action. Includes checklist, "
                    "risk, scope, expected impact, abort conditions, and explicit approval requirement. "
                    "This tool does not execute the proposed action."
                ),
                input_schema={
                    "type": "object",
                    "required": ["proposed_action", "target", "rationale"],
                    "properties": {
                        "proposed_action": {"type": "string", "maxLength": 512},
                        "target": {"type": "string"},
                        "rationale": {"type": "string", "maxLength": 2000},
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "default": "high",
                        },
                        "expected_impact": {"type": "string", "maxLength": 2000},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                        "rollback_plan": {"type": "string", "maxLength": 2000},
                        "operator": {"type": "string", "maxLength": 128},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_fire_control,
                tags=["analysis", "helper", "audit", "approval"],
                when_to_use=[
                    "Before implant generation, credential dumping, session execution, destructive validation, or noisy AD actions.",
                    "When an LLM has enough evidence to recommend action but must hand control to a human.",
                ],
                pitfalls=[
                    "This packet is not approval. Human approval happens outside the tool result.",
                    "If scope or rollback is missing, stop and ask instead of executing anything.",
                ],
                local_model_hints=(
                    "After this tool returns, wait. Do not call the proposed tool unless the human explicitly approves."
                ),
            ),
            ToolSpec(
                name="zero_day_hypothesis",
                description=(
                    "Package suspected unknown-vulnerability behavior into a safe hypothesis record with "
                    "reproduction notes, evidence gaps, and non-weaponized next experiments. This tool "
                    "does not execute validation or generate exploit code."
                ),
                input_schema={
                    "type": "object",
                    "required": ["title", "target", "observed_behavior"],
                    "properties": {
                        "title": {"type": "string", "maxLength": 256},
                        "target": {"type": "string"},
                        "observed_behavior": {"type": "string", "maxLength": 4000},
                        "reproduction_conditions": {"type": "array", "items": {"type": "string"}},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                        "impact_hypothesis": {"type": "string", "maxLength": 2000},
                        "negative_controls": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_zero_day,
                tags=["analysis", "helper", "audit"],
                when_to_use=[
                    "Verified high-impact behavior has no known CVE/template match.",
                    "Operator needs an isolated reproduction plan and evidence checklist.",
                ],
                pitfalls=[
                    "Do not generate exploit code, bypasses, payloads, or public disclosure text.",
                    "Keep reproduction notes isolated to authorized lab or engagement systems.",
                ],
                local_model_hints="Frame hypotheses and evidence. Do not weaponize.",
            ),
            ToolSpec(
                name="evidence_pack",
                description=(
                    "Assemble findings, tool outputs, and references into a structured operator/reporting "
                    "pack. This tool does not execute tools or alter evidence."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "default": "Evidence Pack"},
                        "scope": {"type": "string"},
                        "findings": {"type": "array", "items": {"type": "object"}},
                        "tool_outputs": {"type": "array", "items": {"type": "object"}},
                        "references": {"type": "array", "items": {"type": "string"}},
                        "redaction_level": {
                            "type": "string",
                            "enum": ["summary", "sanitized", "raw"],
                            "default": "sanitized",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_evidence_pack,
                tags=["analysis", "helper", "audit", "report"],
                when_to_use=[
                    "Before writing a report or handing findings to another operator.",
                    "When sensitive tool output needs a structured summary and redaction reminder.",
                ],
                pitfalls=[
                    "Raw mode may expose secrets; prefer sanitized unless the human explicitly asks."
                ],
                local_model_hints="Summarize and structure evidence. Do not paste secrets unless requested.",
            ),
        ]

    async def _handle_triage(self, args: dict[str, Any]) -> ToolResult:
        finding = await self._resolve_finding(args)
        if finding is None:
            return ToolResult.error("Provide either finding_id or finding.")
        enrichment = _mapping(args.get("enrichment"))
        if args.get("enrich_cves"):
            cves = _finding_cves(finding)
            if cves:
                records = await CVEEnrichmentClient().enrich(cves)
                enrichment = {cve: record.as_readiness_record() for cve, record in records.items()}
        assessment = assess_exploitability(
            finding,
            enrichment=enrichment,
            context=_mapping(args.get("context")),
        )
        structured = _assessment_to_dict(assessment)
        return ToolResult(
            text=(
                f"Readiness: {assessment.rating.value} score={assessment.score}/100 "
                f"confidence={assessment.confidence}; approval_required={assessment.requires_human_approval}."
            ),
            structured=structured,
        )

    async def _handle_attack_path(self, args: dict[str, Any]) -> ToolResult:
        findings = [_mapping(item) for item in args["findings"] if isinstance(item, dict)]
        context = _mapping(args.get("context"))
        ranked = sorted(
            (assess_exploitability(f, context=context) for f in findings),
            key=lambda item: item.score,
            reverse=True,
        )
        steps = [
            _plan_step(i + 1, assessment)
            for i, assessment in enumerate(ranked[: int(args.get("max_steps") or 5)])
        ]
        return ToolResult(
            text=f"Built advisory attack path with {len(steps)} step(s). Human approval required before active validation.",
            structured={
                "target": args.get("target"),
                "steps": steps,
                "approval_required_before_execution": True,
                "non_execution_notice": "This plan does not execute tools or payloads.",
            },
        )

    async def _handle_fire_control(self, args: dict[str, Any]) -> ToolResult:
        risk = str(args.get("risk_level") or "high")
        missing = [
            name
            for name in ("expected_impact", "rollback_plan")
            if not str(args.get(name) or "").strip()
        ]
        checklist = [
            "Scope and rules of engagement confirmed by a human.",
            "Target, action, expected impact, and abort conditions understood.",
            "Evidence references reviewed and sufficient.",
            "Rollback or cleanup plan accepted.",
            "Operator explicitly approves the next tool call outside this packet.",
        ]
        return ToolResult(
            text=f"Fire-control packet prepared for {args['proposed_action']!r}; explicit human approval required.",
            structured={
                "approval_required": True,
                "approved": False,
                "proposed_action": args["proposed_action"],
                "target": args["target"],
                "risk_level": risk,
                "rationale": args["rationale"],
                "expected_impact": args.get("expected_impact", ""),
                "evidence_refs": args.get("evidence_refs", []),
                "rollback_plan": args.get("rollback_plan", ""),
                "operator": args.get("operator", ""),
                "missing_before_approval": missing,
                "checklist": checklist,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "next_state": "wait_for_human_approval",
            },
        )

    async def _handle_zero_day(self, args: dict[str, Any]) -> ToolResult:
        evidence_refs = [str(x) for x in args.get("evidence_refs", [])]
        conditions = [str(x) for x in args.get("reproduction_conditions", [])]
        controls = [str(x) for x in args.get("negative_controls", [])]
        gaps = []
        if not evidence_refs:
            gaps.append("sanitized request/response, crash log, screenshot, or tool output")
        if not conditions:
            gaps.append("minimal reproduction conditions")
        if not controls:
            gaps.append("negative controls proving the behavior is not normal")
        return ToolResult(
            text=f"Zero-day hypothesis packaged: {args['title']}. Keep work isolated and non-weaponized.",
            structured={
                "title": args["title"],
                "target": args["target"],
                "observed_behavior": args["observed_behavior"],
                "impact_hypothesis": args.get("impact_hypothesis", ""),
                "reproduction_conditions": conditions,
                "negative_controls": controls,
                "evidence_refs": evidence_refs,
                "evidence_gaps": gaps,
                "safe_next_experiments": [
                    "Minimize reproduction in an isolated authorized environment.",
                    "Capture sanitized request/response and version fingerprints.",
                    "Compare patched, unpatched, and unrelated control targets when available.",
                    "Prepare coordinated disclosure notes only after human review.",
                ],
                "do_not": [
                    "Do not generate exploit code or payloads.",
                    "Do not test outside authorized scope.",
                    "Do not publish details before owner approval.",
                ],
            },
        )

    async def _handle_evidence_pack(self, args: dict[str, Any]) -> ToolResult:
        findings = [item for item in args.get("findings", []) if isinstance(item, dict)]
        outputs = [item for item in args.get("tool_outputs", []) if isinstance(item, dict)]
        severity_counts: dict[str, int] = {}
        for finding in findings:
            severity = str(finding.get("severity") or "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return ToolResult(
            text=f"Evidence pack '{args.get('title', 'Evidence Pack')}' assembled with {len(findings)} finding(s).",
            structured={
                "title": args.get("title", "Evidence Pack"),
                "scope": args.get("scope", ""),
                "findings_count": len(findings),
                "tool_outputs_count": len(outputs),
                "severity_counts": severity_counts,
                "findings": findings,
                "tool_outputs": outputs,
                "references": args.get("references", []),
                "redaction_level": args.get("redaction_level", "sanitized"),
                "handling_notes": [
                    "Prefer sanitized evidence for chat/report transfer.",
                    "Keep secrets, hashes, cookies, tokens, and payloads out of raw chat unless explicitly requested.",
                ],
            },
        )

    async def _resolve_finding(self, args: dict[str, Any]) -> dict[str, Any] | ent.Finding | None:
        if args.get("finding"):
            return _mapping(args["finding"])
        if not args.get("finding_id"):
            return None
        ctx = current_context_or_none()
        if ctx is None:
            return None
        return await ctx.finding.get(UUID(str(args["finding_id"])))


def _assessment_to_dict(assessment: ReadinessAssessment) -> dict[str, Any]:
    return {
        "score": assessment.score,
        "rating": assessment.rating.value,
        "confidence": assessment.confidence,
        "requires_human_approval": assessment.requires_human_approval,
        "cves": list(assessment.cves),
        "signals": [signal.__dict__ for signal in assessment.signals],
        "evidence_gaps": list(assessment.evidence_gaps),
        "recommended_next_steps": list(assessment.recommended_next_steps),
        "safety_gates": list(assessment.safety_gates),
    }


def _plan_step(index: int, assessment: ReadinessAssessment) -> dict[str, Any]:
    if assessment.rating.value == "operator_review":
        tool_hint = "operator_fire_control"
        action = "Prepare approval packet before any active validation."
    elif assessment.rating.value == "ready_to_validate":
        tool_hint = "nuclei_scan / ffuf / nmap with scoped validation only"
        action = "Validate safely and attach evidence."
    elif assessment.rating.value == "investigate":
        tool_hint = "httpx_probe / nmap_scan / evidence_pack"
        action = "Gather missing version, exposure, and proof."
    else:
        tool_hint = "evidence_pack"
        action = "Park unless new evidence changes priority."
    return {
        "step": index,
        "rating": assessment.rating.value,
        "score": assessment.score,
        "suggested_tool": tool_hint,
        "operator_action": action,
        "evidence_gaps": list(assessment.evidence_gaps),
        "approval_required": assessment.requires_human_approval,
    }


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _finding_cves(finding: dict[str, Any] | ent.Finding) -> list[str]:
    if isinstance(finding, ent.Finding):
        return list(finding.cve)
    values = finding.get("cve") or finding.get("cves") or []
    if isinstance(values, list):
        return [str(v) for v in values]
    if isinstance(values, str):
        return [values]
    return []
