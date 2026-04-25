"""Server dispatch tests for ToolInvocation persistence."""

from __future__ import annotations

import os

import pytest
from mcp.types import CallToolRequest
from sqlalchemy import select

from kestrel_mcp.config import Settings
from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.storage import ToolInvocationRow
from kestrel_mcp.server import RedTeamMCPServer

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
    return await container.engagement.create(
        name="dispatch",
        display_name="Dispatch",
        engagement_type=ent.EngagementType.CTF,
        client="client",
    )


async def _call_tool(
    server: RedTeamMCPServer,
    *,
    name: str,
    arguments: dict[str, object],
):
    mcp = server.build()
    handler = mcp.request_handlers[CallToolRequest]
    request = CallToolRequest(params={"name": name, "arguments": arguments})
    return await handler(request)


async def _rows(container: ServiceContainer) -> list[ToolInvocationRow]:
    async with container.sessionmaker() as session:
        result = await session.execute(
            select(ToolInvocationRow).order_by(ToolInvocationRow.completed_at)
        )
        return list(result.scalars())


async def test_server_records_successful_tool_calls(container, monkeypatch) -> None:
    engagement = await _engagement(container)
    monkeypatch.setenv("KESTREL_ENGAGEMENT", engagement.name)
    server = RedTeamMCPServer(Settings.build(edition="pro"), container=container)

    await _call_tool(
        server,
        name="generate_pentest_report",
        arguments={
            "title": "Dispatch",
            "scope": "*.lab.test",
            "findings": [],
        },
    )

    row = (await _rows(container))[-1]
    assert row.tool_name == "generate_pentest_report"
    assert row.exit_code == 0
    assert row.error_code is None
    assert os.environ["KESTREL_ENGAGEMENT"] == engagement.name


async def test_server_records_handled_tool_errors(container, monkeypatch) -> None:
    engagement = await _engagement(container)
    monkeypatch.setenv("KESTREL_ENGAGEMENT", engagement.name)
    server = RedTeamMCPServer(Settings.build(edition="pro"), container=container)

    await _call_tool(
        server,
        name="engagement_show",
        arguments={"id_or_name": "missing"},
    )

    row = (await _rows(container))[-1]
    assert row.tool_name == "engagement_show"
    assert row.exit_code == 1
    assert row.error_code is None


async def test_server_records_exception_failures(container, monkeypatch) -> None:
    engagement = await _engagement(container)
    monkeypatch.setenv("KESTREL_ENGAGEMENT", engagement.name)
    server = RedTeamMCPServer(Settings.build(edition="pro"), container=container)

    await _call_tool(
        server,
        name="finding_show",
        arguments={"finding_id": "not-a-uuid"},
    )

    row = (await _rows(container))[-1]
    assert row.tool_name == "finding_show"
    assert row.exit_code == 1
    assert row.error_code == "ValueError"
