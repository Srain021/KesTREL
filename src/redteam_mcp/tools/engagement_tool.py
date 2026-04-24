"""EngagementModule — MCP tools that manage engagements, scope, targets, findings.

These tools let the LLM (or human via CLI) drive the domain layer without
leaving the chat. They consume the :class:`~redteam_mcp.core.ServiceContainer`
accessed through :func:`current_context`.

Exposed tools (16)::

    engagement_new          engagement_list        engagement_show
    engagement_activate     engagement_pause       engagement_close
    engagement_switch

    scope_add               scope_remove           scope_list
    scope_check

    target_add              target_list

    finding_list            finding_show           finding_transition

Rationale for a single module (vs split files): all four entity groups
share the same dependency surface and life-cycle assumptions, so keeping
them colocated avoids churn in ``tools/__init__.py`` as we extend them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from ..core.context import (
    NoActiveEngagementError,
    current_context,
    current_context_or_none,
)
from ..domain import entities as ent
from ..domain.errors import (
    DomainError,
    EngagementNotFoundError,
    InvalidStateTransitionError,
    ScopeViolationError,
    UniqueConstraintError,
)
from .base import ToolModule, ToolResult, ToolSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_ctx() -> "RequestContext":  # type: ignore[name-defined]
    ctx = current_context_or_none()
    if ctx is None:
        raise RuntimeError(
            "engagement tools require a RequestContext. "
            "This should be wired by the MCP server automatically."
        )
    return ctx


def _engagement_to_dict(e: ent.Engagement) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "name": e.name,
        "display_name": e.display_name,
        "status": e.status.value,
        "engagement_type": e.engagement_type.value,
        "client": e.client,
        "started_at": e.started_at.isoformat() if e.started_at else None,
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        "dry_run": e.dry_run,
        "opsec_mode": e.opsec_mode,
    }


def _scope_entry_to_dict(s: ent.ScopeEntry) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "pattern": s.pattern,
        "kind": s.kind.value,
        "included": s.included,
        "note": s.note,
        "added_at": s.added_at.isoformat(),
    }


def _target_to_dict(t: ent.Target) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "kind": t.kind.value,
        "value": t.value,
        "open_ports": t.open_ports,
        "tech_stack": t.tech_stack,
        "hostnames": t.hostnames,
        "organization": t.organization,
        "country": t.country,
        "discovered_by_tool": t.discovered_by_tool,
        "discovered_at": t.discovered_at.isoformat(),
        "last_scanned_at": t.last_scanned_at.isoformat() if t.last_scanned_at else None,
    }


def _finding_to_dict(f: ent.Finding) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "target_id": str(f.target_id),
        "title": f.title,
        "severity": f.severity.value,
        "status": f.status.value,
        "confidence": f.confidence.value,
        "category": f.category.value,
        "cwe": f.cwe,
        "cve": f.cve,
        "discovered_by_tool": f.discovered_by_tool,
        "discovered_at": f.discovered_at.isoformat(),
    }


async def _resolve_engagement(ctx, id_or_name: str | None) -> ent.Engagement:
    """Locate an engagement by UUID string, slug, or the active context."""

    if id_or_name is None:
        # use active
        eid = ctx.require_engagement()
        return await ctx.engagement.get(eid)

    # try UUID
    try:
        return await ctx.engagement.get(UUID(id_or_name))
    except ValueError:
        pass

    return await ctx.engagement.get_by_name(id_or_name)


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------


class EngagementModule(ToolModule):
    id = "engagement"

    def enabled(self) -> bool:
        # Always on when a ServiceContainer is configured. We don't gate
        # behind config.tools.engagement.enabled because these are management
        # primitives every user needs.
        return True

    # Module-level id is "engagement"; per-config key under tools.engagement
    # is respected if present but defaults to True.
    # (For future extensibility.)

    def specs(self) -> list[ToolSpec]:
        return [
            # ---- engagement lifecycle ----
            *self._engagement_specs(),
            # ---- scope ----
            *self._scope_specs(),
            # ---- targets ----
            *self._target_specs(),
            # ---- findings ----
            *self._finding_specs(),
        ]

    # ----------------------------------------------------------------
    # Engagement lifecycle
    # ----------------------------------------------------------------

    def _engagement_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="engagement_new",
                description=(
                    "Create a new engagement in PLANNING state. An engagement is "
                    "the top-level container for scope, targets, findings, and "
                    "credentials. Every offensive action must belong to one."
                ),
                input_schema={
                    "type": "object",
                    "required": ["name", "display_name", "engagement_type", "client"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "pattern": "^[a-z0-9_-]{1,64}$",
                            "description": "Short slug. Lowercase letters, digits, '-', '_' only.",
                        },
                        "display_name": {"type": "string", "maxLength": 128},
                        "engagement_type": {
                            "type": "string",
                            "enum": [t.value for t in ent.EngagementType],
                        },
                        "client": {"type": "string", "maxLength": 128},
                        "expires_at_iso": {
                            "type": "string",
                            "format": "date-time",
                            "description": "ISO-8601 UTC timestamp after which dangerous tools are refused.",
                        },
                        "authorization_doc_ref": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_new,
                tags=["engagement", "admin"],
                when_to_use=[
                    "User starts a new CTF box / red-team cycle / pentest.",
                    "Switching clients and need a clean slate.",
                ],
                when_not_to_use=[
                    "Just need a temporary ad-hoc scope entry - use scope_add on the active engagement instead.",
                ],
                follow_ups=[
                    "Call scope_add to declare authorized targets.",
                    "Call engagement_activate to move to ACTIVE.",
                ],
                pitfalls=[
                    "Name must match /^[a-z0-9_-]{1,64}$/. 'HTB-S7' will be rejected; use 'htb-s7'.",
                    "engagement_type is an enum; misspelling returns an error.",
                ],
                local_model_hints=(
                    "Default engagement_type='ctf' when in doubt. "
                    "Prompt the user to confirm display_name and client before calling."
                ),
            ),
            ToolSpec(
                name="engagement_list",
                description="List engagements. Filter by status if provided.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": [s.value for s in ent.EngagementStatus],
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_list,
                tags=["engagement"],
                when_to_use=[
                    "User asks 'what engagements do I have' / 'show all projects'.",
                    "Before engagement_switch to see options.",
                ],
            ),
            ToolSpec(
                name="engagement_show",
                description=(
                    "Show detailed info for one engagement. If id_or_name is "
                    "omitted, returns the active engagement."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "id_or_name": {
                            "type": "string",
                            "description": "UUID string OR slug. Omit to show the current active engagement.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_show,
                tags=["engagement"],
                follow_ups=[
                    "Use scope_list and finding_list to drill into details.",
                ],
            ),
            ToolSpec(
                name="engagement_activate",
                description=(
                    "Move an engagement from PLANNING or PAUSED to ACTIVE. "
                    "Dangerous tools only run against ACTIVE engagements."
                ),
                input_schema={
                    "type": "object",
                    "required": ["id_or_name"],
                    "properties": {"id_or_name": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_activate,
                tags=["engagement", "lifecycle"],
                pitfalls=[
                    "Cannot activate a CLOSED engagement - it is terminal.",
                ],
            ),
            ToolSpec(
                name="engagement_pause",
                description="Pause an active engagement. Dangerous tools will refuse.",
                input_schema={
                    "type": "object",
                    "required": ["id_or_name"],
                    "properties": {"id_or_name": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_pause,
                tags=["engagement", "lifecycle"],
            ),
            ToolSpec(
                name="engagement_close",
                description="Close an engagement. IRREVERSIBLE. Preserves all data.",
                input_schema={
                    "type": "object",
                    "required": ["id_or_name", "confirm"],
                    "properties": {
                        "id_or_name": {"type": "string"},
                        "confirm": {
                            "type": "boolean",
                            "description": "Must be true to proceed. Safety guard.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_close,
                dangerous=True,
                tags=["engagement", "lifecycle"],
                pitfalls=[
                    "Terminal state - cannot be re-opened. Export data first if needed.",
                ],
                local_model_hints=(
                    "NEVER call without confirm=true. If the user asked to close an engagement, "
                    "summarise what will happen and ask for explicit yes before sending confirm=true."
                ),
            ),
            ToolSpec(
                name="engagement_switch",
                description=(
                    "NOT persisted — switch the ACTIVE engagement for the current "
                    "session by updating an environment variable hint. "
                    "In practice, the MCP host should call this with _engagement "
                    "injected per request. This tool echoes intent so the host "
                    "can update its configuration."
                ),
                input_schema={
                    "type": "object",
                    "required": ["id_or_name"],
                    "properties": {"id_or_name": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_switch,
                tags=["engagement", "session"],
                local_model_hints=(
                    "This tool cannot permanently change the active engagement across server "
                    "restarts. Tell the user to update KESTREL_ENGAGEMENT env var or mcp.json "
                    "if they want persistence."
                ),
            ),
        ]

    async def _handle_new(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            expires_at = None
            if iso := args.get("expires_at_iso"):
                expires_at = datetime.fromisoformat(iso).astimezone(timezone.utc)

            e = await ctx.engagement.create(
                name=args["name"],
                display_name=args["display_name"],
                engagement_type=ent.EngagementType(args["engagement_type"]),
                client=args["client"],
                authorization_doc_ref=args.get("authorization_doc_ref"),
                expires_at=expires_at,
            )
        except UniqueConstraintError as exc:
            return ToolResult.error(str(exc))
        except DomainError as exc:
            return ToolResult.error(str(exc))

        return ToolResult(
            text=f"Engagement '{e.name}' created (id={e.id}). State: {e.status.value}.",
            structured=_engagement_to_dict(e),
        )

    async def _handle_list(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        status = ent.EngagementStatus(args["status"]) if args.get("status") else None
        es = await ctx.engagement.list(status=status)
        return ToolResult(
            text=f"{len(es)} engagement(s).",
            structured={
                "count": len(es),
                "engagements": [_engagement_to_dict(e) for e in es],
            },
        )

    async def _handle_show(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            e = await _resolve_engagement(ctx, args.get("id_or_name"))
        except (EngagementNotFoundError, NoActiveEngagementError) as exc:
            return ToolResult.error(str(exc))
        scope_entries = await ctx.scope.list_entries(e.id)
        return ToolResult(
            text=f"Engagement '{e.name}' (id={e.id}), status={e.status.value}, scope={len(scope_entries)} entries.",
            structured={
                **_engagement_to_dict(e),
                "scope": [_scope_entry_to_dict(s) for s in scope_entries],
            },
        )

    async def _handle_activate(self, args: dict[str, Any]) -> ToolResult:
        return await self._transition(args, ent.EngagementStatus.ACTIVE)

    async def _handle_pause(self, args: dict[str, Any]) -> ToolResult:
        return await self._transition(args, ent.EngagementStatus.PAUSED)

    async def _handle_close(self, args: dict[str, Any]) -> ToolResult:
        if not args.get("confirm"):
            return ToolResult.error(
                "engagement_close requires confirm=true. Close is terminal; re-send with confirm to proceed."
            )
        return await self._transition(args, ent.EngagementStatus.CLOSED)

    async def _transition(
        self,
        args: dict[str, Any],
        to_status: ent.EngagementStatus,
    ) -> ToolResult:
        ctx = _require_ctx()
        try:
            e = await _resolve_engagement(ctx, args["id_or_name"])
            e = await ctx.engagement.transition(e.id, to_status)
        except (EngagementNotFoundError, InvalidStateTransitionError) as exc:
            return ToolResult.error(str(exc))
        return ToolResult(
            text=f"Engagement '{e.name}' transitioned to {e.status.value}.",
            structured=_engagement_to_dict(e),
        )

    async def _handle_switch(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            e = await _resolve_engagement(ctx, args["id_or_name"])
        except EngagementNotFoundError as exc:
            return ToolResult.error(str(exc))
        return ToolResult(
            text=(
                f"Engagement '{e.name}' (id={e.id}) acknowledged for switch. "
                "To make this permanent across restarts, set "
                f"KESTREL_ENGAGEMENT={e.name} or pass _engagement={e.id} per call."
            ),
            structured={
                "hint_env": f"KESTREL_ENGAGEMENT={e.name}",
                "hint_arg": {"_engagement": str(e.id)},
                "target": _engagement_to_dict(e),
            },
        )

    # ----------------------------------------------------------------
    # Scope
    # ----------------------------------------------------------------

    def _scope_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="scope_add",
                description=(
                    "Add an authorized-scope entry to the active engagement. "
                    "Supports exact hostname, *.wildcard, .apex-wildcard, IPv4/6, CIDR, URL."
                ),
                input_schema={
                    "type": "object",
                    "required": ["pattern"],
                    "properties": {
                        "pattern": {"type": "string", "maxLength": 256},
                        "included": {
                            "type": "boolean",
                            "default": True,
                            "description": "False creates an EXCLUSION (higher priority).",
                        },
                        "note": {"type": "string", "maxLength": 512},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_scope_add,
                tags=["scope", "admin"],
                when_to_use=[
                    "Immediately after engagement_new, before any scans.",
                    "Expanding scope mid-engagement (with authorization).",
                    "Adding EXCLUSIONS for sensitive in-scope subdomains.",
                ],
                pitfalls=[
                    "Requires an active engagement - call engagement_switch first.",
                    "'*.example.com' does NOT match 'example.com' apex. Use '.example.com' for both.",
                ],
            ),
            ToolSpec(
                name="scope_remove",
                description="Remove matching entries from the active engagement's scope.",
                input_schema={
                    "type": "object",
                    "required": ["pattern"],
                    "properties": {"pattern": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_scope_remove,
                tags=["scope", "admin"],
            ),
            ToolSpec(
                name="scope_list",
                description="List scope entries for the active engagement.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_scope_list,
                tags=["scope"],
            ),
            ToolSpec(
                name="scope_check",
                description=(
                    "Check whether a target would be allowed under the current engagement's "
                    "scope. Does NOT perform any network action."
                ),
                input_schema={
                    "type": "object",
                    "required": ["target"],
                    "properties": {"target": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_scope_check,
                tags=["scope", "audit"],
            ),
        ]

    async def _handle_scope_add(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        entry = await ctx.scope.add_entry(
            eid,
            args["pattern"],
            included=args.get("included", True),
            note=args.get("note"),
        )
        return ToolResult(
            text=f"Scope entry '{entry.pattern}' added ({entry.kind.value}, included={entry.included}).",
            structured=_scope_entry_to_dict(entry),
        )

    async def _handle_scope_remove(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        removed = await ctx.scope.remove_entry(eid, args["pattern"])
        return ToolResult(
            text=f"Removed {removed} entry(ies) matching '{args['pattern']}'.",
            structured={"removed": removed, "pattern": args["pattern"]},
        )

    async def _handle_scope_list(self, _args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        entries = await ctx.scope.list_entries(eid)
        return ToolResult(
            text=f"{len(entries)} scope entry(ies).",
            structured={
                "count": len(entries),
                "entries": [_scope_entry_to_dict(e) for e in entries],
            },
        )

    async def _handle_scope_check(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        try:
            await ctx.scope.ensure(eid, args["target"], tool_name="scope_check")
        except ScopeViolationError as exc:
            return ToolResult(
                text=f"NOT IN SCOPE: {args['target']}",
                structured={"in_scope": False, "reason": str(exc), "target": args["target"]},
            )
        return ToolResult(
            text=f"IN SCOPE: {args['target']}",
            structured={"in_scope": True, "target": args["target"]},
        )

    # ----------------------------------------------------------------
    # Targets
    # ----------------------------------------------------------------

    def _target_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="target_add",
                description=(
                    "Add a target (asset) to the active engagement. Idempotent on "
                    "(kind, value). Also enforces the engagement scope."
                ),
                input_schema={
                    "type": "object",
                    "required": ["kind", "value"],
                    "properties": {
                        "kind": {"type": "string", "enum": [k.value for k in ent.TargetKind]},
                        "value": {"type": "string", "maxLength": 512},
                        "discovered_by_tool": {"type": "string", "maxLength": 128},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_target_add,
                dangerous=True,  # can grow the asset inventory - treat cautiously
                requires_scope_field="value",
                tags=["target", "admin"],
            ),
            ToolSpec(
                name="target_list",
                description="List targets in the active engagement. Filter by kind.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": [k.value for k in ent.TargetKind]},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_target_list,
                tags=["target"],
            ),
        ]

    async def _handle_target_add(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        # Scope check was already performed by the server dispatcher
        # via requires_scope_field="value"; nothing to do here.
        t = await ctx.target.add(
            engagement_id=eid,
            kind=ent.TargetKind(args["kind"]),
            value=args["value"],
            discovered_by_tool=args.get("discovered_by_tool"),
        )
        return ToolResult(
            text=f"Target '{t.value}' added ({t.kind.value}).",
            structured=_target_to_dict(t),
        )

    async def _handle_target_list(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        kind = ent.TargetKind(args["kind"]) if args.get("kind") else None
        targets = await ctx.target.list_for_engagement(eid, kind=kind)
        return ToolResult(
            text=f"{len(targets)} target(s).",
            structured={
                "count": len(targets),
                "targets": [_target_to_dict(t) for t in targets],
            },
        )

    # ----------------------------------------------------------------
    # Findings
    # ----------------------------------------------------------------

    def _finding_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="finding_list",
                description="List findings in the active engagement, with optional filters.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": [s.value for s in ent.FindingStatus],
                        },
                        "severity": {
                            "type": "string",
                            "enum": [s.value for s in ent.FindingSeverity],
                        },
                        "target_id": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_finding_list,
                tags=["finding"],
            ),
            ToolSpec(
                name="finding_show",
                description="Return a single finding's full detail.",
                input_schema={
                    "type": "object",
                    "required": ["finding_id"],
                    "properties": {"finding_id": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_finding_show,
                tags=["finding"],
            ),
            ToolSpec(
                name="finding_transition",
                description=(
                    "Move a finding through its state machine: "
                    "NEW → TRIAGED → CONFIRMED → FIXED (or FALSE_POSITIVE / CLOSED_WONTFIX)."
                ),
                input_schema={
                    "type": "object",
                    "required": ["finding_id", "to_status"],
                    "properties": {
                        "finding_id": {"type": "string"},
                        "to_status": {
                            "type": "string",
                            "enum": [s.value for s in ent.FindingStatus],
                        },
                        "note": {"type": "string", "maxLength": 2048},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_finding_transition,
                tags=["finding", "lifecycle"],
                pitfalls=[
                    "State machine is strict: NEW cannot jump directly to FIXED.",
                    "FIXED / FALSE_POSITIVE / CLOSED_WONTFIX are terminal.",
                ],
            ),
        ]

    async def _handle_finding_list(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            eid = ctx.require_engagement()
        except NoActiveEngagementError as exc:
            return ToolResult.error(str(exc))
        kwargs: dict[str, Any] = {}
        if s := args.get("status"):
            kwargs["status"] = ent.FindingStatus(s)
        if s := args.get("severity"):
            kwargs["severity"] = ent.FindingSeverity(s)
        if t := args.get("target_id"):
            kwargs["target_id"] = UUID(t)
        findings = await ctx.finding.list_for_engagement(eid, **kwargs)
        return ToolResult(
            text=f"{len(findings)} finding(s).",
            structured={
                "count": len(findings),
                "by_severity": {
                    sev.value: sum(1 for f in findings if f.severity == sev)
                    for sev in ent.FindingSeverity
                    if any(f.severity == sev for f in findings)
                },
                "findings": [_finding_to_dict(f) for f in findings],
            },
        )

    async def _handle_finding_show(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        f = await ctx.finding.get(UUID(args["finding_id"]))
        if f is None:
            return ToolResult.error(f"Finding {args['finding_id']} not found.")
        return ToolResult(
            text=f"{f.title} [{f.severity.value}] on target={f.target_id}",
            structured=_finding_to_dict(f)
            | {
                "description": f.description,
                "impact": f.impact,
                "remediation": f.remediation,
                "cvss_vector": f.cvss_vector,
                "cvss_score": f.cvss_score,
            },
        )

    async def _handle_finding_transition(self, args: dict[str, Any]) -> ToolResult:
        ctx = _require_ctx()
        try:
            f = await ctx.finding.transition(
                UUID(args["finding_id"]),
                ent.FindingStatus(args["to_status"]),
                note=args.get("note", ""),
            )
        except (InvalidStateTransitionError, ValueError) as exc:
            return ToolResult.error(str(exc))
        return ToolResult(
            text=f"Finding '{f.title}' -> {f.status.value}.",
            structured=_finding_to_dict(f),
        )
