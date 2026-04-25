"""MCP tools for the HARNESS local-model execution layer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from ..config import Settings
from ..core.context import current_context
from ..domain import entities as ent
from ..security import ScopeGuard
from ..tools.base import ToolModule, ToolResult, ToolSpec
from .planner import HarnessPlanner, infer_target

HarnessRunner = Callable[[str, dict[str, Any]], Awaitable[tuple[ToolResult, str | None]]]
SpecProvider = Callable[[], dict[str, ToolSpec]]


class HarnessModule(ToolModule):
    id = "harness"

    def __init__(
        self,
        settings: Settings,
        scope_guard: ScopeGuard,
        *,
        specs_provider: SpecProvider,
        runner: HarnessRunner | None = None,
    ) -> None:
        super().__init__(settings, scope_guard)
        self._specs_provider = specs_provider
        self._runner = runner

    def enabled(self) -> bool:
        return True

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="harness_start",
                description="Create a persisted HARNESS session for a local or mixed-model task.",
                input_schema={
                    "type": "object",
                    "required": ["goal"],
                    "properties": {
                        "goal": {"type": "string"},
                        "target": {"type": "string"},
                        "engagement": {"type": "string"},
                        "mode": {"type": "string", "default": "recon"},
                        "model_tier": {
                            "type": "string",
                            "enum": ["local", "standard", "strong"],
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start,
                tags=["harness", "workflow"],
                phase="workflow",
                complexity_tier=1,
                preferred_model_tier="local",
            ),
            ToolSpec(
                name="harness_next",
                description="Return the next single HARNESS step for a session.",
                input_schema={
                    "type": "object",
                    "required": ["session_id"],
                    "properties": {"session_id": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_next,
                tags=["harness", "workflow"],
                phase="workflow",
                complexity_tier=0,
                preferred_model_tier="local",
            ),
            ToolSpec(
                name="harness_run",
                description="Run one planned HARNESS step through the central tool dispatcher.",
                input_schema={
                    "type": "object",
                    "required": ["session_id", "step_id"],
                    "properties": {
                        "session_id": {"type": "string"},
                        "step_id": {"type": "string"},
                        "confirm": {"type": "boolean", "default": False},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_run,
                tags=["harness", "workflow"],
                phase="workflow",
                complexity_tier=1,
                preferred_model_tier="local",
            ),
            ToolSpec(
                name="harness_state",
                description="Return persisted HARNESS session state and step history.",
                input_schema={
                    "type": "object",
                    "required": ["session_id"],
                    "properties": {"session_id": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_state,
                tags=["harness", "workflow"],
                phase="workflow",
                complexity_tier=0,
                preferred_model_tier="local",
            ),
        ]

    async def _handle_start(self, args: dict[str, Any]) -> ToolResult:
        ctx = current_context()
        goal = str(args["goal"])
        target = args.get("target") or infer_target(goal)
        engagement_id = await self._resolve_engagement(args.get("engagement"))
        if engagement_id is None and ctx.engagement_id is not None:
            engagement_id = ctx.engagement_id
        session = await ctx.harness.create_session(
            goal=goal,
            target=str(target) if target else None,
            engagement_id=engagement_id,
            mode=str(args.get("mode") or "recon"),
            model_tier=str(args.get("model_tier") or self.settings.llm.model_tier),
        )
        step = await self._ensure_next(session.id)
        return ToolResult(
            text=f"HARNESS session {session.id} created.",
            structured={
                "session": session.model_dump(mode="json"),
                "next_step": _step_payload(step) if step else None,
            },
        )

    async def _handle_next(self, args: dict[str, Any]) -> ToolResult:
        session_id = UUID(str(args["session_id"]))
        step = await self._ensure_next(session_id)
        if step is None:
            return ToolResult(
                text="No HARNESS next step is available.",
                structured={"session_id": str(session_id), "next_step": None},
            )
        return ToolResult(
            text=f"Next HARNESS step: {step.tool_name}.", structured=_step_payload(step)
        )

    async def _handle_run(self, args: dict[str, Any]) -> ToolResult:
        if self._runner is None:
            return ToolResult.error("HARNESS runner is not wired in this process.")

        ctx = current_context()
        session_id = UUID(str(args["session_id"]))
        step_id = UUID(str(args["step_id"]))
        step = await ctx.harness.get_step(step_id)
        if step is None or step.session_id != session_id:
            return ToolResult.error(f"HARNESS step {step_id} not found for session {session_id}.")
        if step.tool_name.startswith("harness_"):
            return ToolResult.error("HARNESS will not recursively run harness_* tools.")

        confirm = bool(args.get("confirm", False))
        if step.status == ent.HarnessStepStatus.NEEDS_CONFIRMATION and not confirm:
            return ToolResult.error(
                "This HARNESS step requires confirm=true.",
                **_step_payload(step),
            )

        await ctx.harness.update_step(step.id, status=ent.HarnessStepStatus.RUNNING)
        result, invocation_id = await self._runner(step.tool_name, dict(step.arguments))
        summary = _summarize_result(result)
        status = ent.HarnessStepStatus.FAILED if result.is_error else ent.HarnessStepStatus.DONE
        updated = await ctx.harness.update_step(
            step.id,
            status=status,
            result_summary=summary,
            tool_invocation_id=UUID(invocation_id) if invocation_id else None,
        )
        await ctx.harness.update_session(session_id, state_summary=summary)
        return ToolResult(
            text=f"HARNESS ran {step.tool_name}: {'failed' if result.is_error else 'done'}.",
            structured={
                "step": _step_payload(updated or step),
                "tool_result": {
                    "text": result.text,
                    "structured": result.structured,
                    "is_error": result.is_error,
                },
            },
            is_error=result.is_error,
        )

    async def _handle_state(self, args: dict[str, Any]) -> ToolResult:
        ctx = current_context()
        session_id = UUID(str(args["session_id"]))
        payload = await ctx.harness.get_state_payload(session_id)
        if payload is None:
            return ToolResult.error(f"HARNESS session {session_id} not found.")
        return ToolResult(text=f"HARNESS session {session_id} state.", structured=payload)

    async def _ensure_next(self, session_id: UUID) -> ent.HarnessStep | None:
        ctx = current_context()
        session = await ctx.harness.get_session(session_id)
        if session is None:
            return None
        steps = await ctx.harness.list_steps(session_id)
        for step in steps:
            if step.status in {
                ent.HarnessStepStatus.PENDING,
                ent.HarnessStepStatus.NEEDS_CONFIRMATION,
                ent.HarnessStepStatus.RUNNING,
            }:
                return step
        planned = HarnessPlanner(self._specs_provider()).next_step(session, steps)
        if planned is None:
            await ctx.harness.update_session(session_id, status=ent.HarnessSessionStatus.DONE)
            return None
        status = (
            ent.HarnessStepStatus.NEEDS_CONFIRMATION
            if planned.requires_confirmation
            else ent.HarnessStepStatus.PENDING
        )
        return await ctx.harness.add_step(
            session_id=session_id,
            tool_name=planned.tool_name,
            arguments=dict(planned.arguments),
            status=status,
            risk_level=planned.risk_level,
            recommended_model_tier=planned.recommended_model_tier,
            reason=planned.reason,
        )

    async def _resolve_engagement(self, raw: object) -> UUID | None:
        if not raw:
            return None
        text = str(raw)
        try:
            return UUID(text)
        except ValueError:
            pass
        ctx = current_context()
        engagement = await ctx.engagement.get_by_name(text)
        return engagement.id if engagement else None


def _step_payload(step: ent.HarnessStep) -> dict[str, Any]:
    return {
        "step_id": str(step.id),
        "tool_name": step.tool_name,
        "arguments": step.arguments,
        "why_this_step": step.reason,
        "risk_level": step.risk_level,
        "recommended_model_tier": step.recommended_model_tier,
        "requires_confirmation": step.status == ent.HarnessStepStatus.NEEDS_CONFIRMATION,
        "status": step.status.value if hasattr(step.status, "value") else str(step.status),
        "tool_invocation_id": str(step.tool_invocation_id) if step.tool_invocation_id else None,
    }


def _summarize_result(result: ToolResult) -> str:
    if result.structured:
        for key in ("findings_count", "count"):
            if key in result.structured:
                return f"{result.text} {key}={result.structured[key]}"[:4096]
        for key in ("hosts", "probes", "results", "subdomains"):
            value = result.structured.get(key)
            if isinstance(value, list):
                return f"{result.text} {key}={len(value)}"[:4096]
    return result.text[:4096]
