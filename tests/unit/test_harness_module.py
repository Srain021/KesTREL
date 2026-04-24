from __future__ import annotations

import json

import pytest
from mcp.types import CallToolRequest
from sqlalchemy import select

from kestrel_mcp.config import Settings
from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.storage import ToolInvocationRow
from kestrel_mcp.harness import HarnessModule
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.server import RedTeamMCPServer
from kestrel_mcp.tools.base import ToolResult

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


async def _engagement(container: ServiceContainer) -> ent.Engagement:
    engagement = await container.engagement.create(
        name="harness",
        display_name="Harness",
        engagement_type=ent.EngagementType.CTF,
        client="client",
    )
    await container.scope.add_entry(engagement.id, "*.lab.test")
    return engagement


def _json_block(response) -> dict[str, object]:
    text = response.root.content[-1].text
    assert text.startswith("```json\n")
    return json.loads(text.removeprefix("```json\n").removesuffix("\n```"))


async def _call_tool(server: RedTeamMCPServer, name: str, arguments: dict[str, object]):
    mcp = server.build()
    handler = mcp.request_handlers[CallToolRequest]
    return await handler(CallToolRequest(params={"name": name, "arguments": arguments}))


async def _invocation_rows(container: ServiceContainer) -> list[ToolInvocationRow]:
    async with container.sessionmaker() as session:
        result = await session.execute(select(ToolInvocationRow).order_by(ToolInvocationRow.completed_at))
        return list(result.scalars())


def _spec(module: HarnessModule, name: str):
    for spec in module.specs():
        if spec.name == name:
            return spec
    raise AssertionError(f"missing spec {name}")


async def test_harness_start_next_run_state_records_internal_tool_invocation(
    container,
    monkeypatch,
) -> None:
    engagement = await _engagement(container)
    monkeypatch.setenv("KESTREL_ENGAGEMENT", engagement.name)
    server = RedTeamMCPServer(Settings.build(edition="pro"), container=container)

    started = _json_block(
        await _call_tool(
            server,
            "harness_start",
            {"goal": "Recon api.lab.test", "target": "api.lab.test", "model_tier": "local"},
        )
    )
    session_id = started["session"]["id"]
    next_step = started["next_step"]
    assert next_step["tool_name"] == "scope_check"
    assert next_step["requires_confirmation"] is False

    repeated = _json_block(await _call_tool(server, "harness_next", {"session_id": session_id}))
    assert repeated["step_id"] == next_step["step_id"]

    ran = _json_block(
        await _call_tool(
            server,
            "harness_run",
            {"session_id": session_id, "step_id": next_step["step_id"]},
        )
    )
    assert ran["step"]["status"] == "done"
    assert ran["step"]["tool_invocation_id"]

    state = _json_block(await _call_tool(server, "harness_state", {"session_id": session_id}))
    assert state["steps"][0]["tool_name"] == "scope_check"
    assert state["steps"][0]["tool_invocation_id"] == ran["step"]["tool_invocation_id"]

    rows = await _invocation_rows(container)
    assert "scope_check" in {row.tool_name for row in rows}


async def test_high_risk_harness_step_requires_confirmation(container) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def runner(tool_name: str, arguments: dict[str, object]):
        calls.append((tool_name, arguments))
        return ToolResult(text="ran"), None

    module = HarnessModule(
        Settings.build(),
        ScopeGuard([]),
        specs_provider=lambda: {},
        runner=runner,
    )

    async with container.open_context():
        session = await container.harness.create_session(
            goal="High risk check",
            target="example.com",
            engagement_id=None,
            mode="recon",
            model_tier="strong",
        )
        step = await container.harness.add_step(
            session_id=session.id,
            tool_name="sliver_sessions",
            arguments={},
            status=ent.HarnessStepStatus.NEEDS_CONFIRMATION,
            risk_level="high",
            recommended_model_tier="strong",
            reason="High-risk tool.",
        )

        denied = await _spec(module, "harness_run").handler(
            {"session_id": str(session.id), "step_id": str(step.id)}
        )
        accepted = await _spec(module, "harness_run").handler(
            {"session_id": str(session.id), "step_id": str(step.id), "confirm": True}
        )

    assert denied.is_error
    assert "confirm=true" in denied.text
    assert not accepted.is_error
    assert calls == [("sliver_sessions", {})]
