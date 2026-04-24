from __future__ import annotations

import json

import pytest
from mcp.types import ListResourcesRequest, ReadResourceRequest

from kestrel_mcp import resources
from kestrel_mcp.config import Settings
from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
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
        name="resources",
        display_name="Resources",
        engagement_type=ent.EngagementType.CTF,
        client="client",
    )


async def test_list_all_resources_for_active_engagement(container) -> None:
    engagement = await _engagement(container)

    async with container.open_context(engagement_id=engagement.id):
        items = await resources.list_all_resources()

    uris = {item["uri"] for item in items}
    assert uris == {
        f"engagement://{engagement.id}/summary",
        f"engagement://{engagement.id}/scope",
        f"engagement://{engagement.id}/targets",
        f"engagement://{engagement.id}/findings",
    }


async def test_read_engagement_resources_returns_scope_targets_and_findings(container) -> None:
    engagement = await _engagement(container)
    await container.scope.add_entry(engagement.id, "*.lab.test")
    target = await container.target.add(
        engagement_id=engagement.id,
        kind=ent.TargetKind.HOSTNAME,
        value="app.lab.test",
        discovered_by_tool="httpx_probe",
    )
    await container.finding.create(
        engagement_id=engagement.id,
        target_id=target.id,
        title="Open redirect",
        severity=ent.FindingSeverity.MEDIUM,
        category=ent.FindingCategory.MISCONFIGURATION,
        discovered_by_tool="ffuf_scan",
    )

    async with container.open_context(engagement_id=engagement.id):
        summary = await resources.read_resource(f"engagement://{engagement.id}/summary")
        scope = await resources.read_resource(f"engagement://{engagement.id}/scope")
        targets = await resources.read_resource(f"engagement://{engagement.id}/targets")
        findings = await resources.read_resource(f"engagement://{engagement.id}/findings")

    assert summary is not None
    assert scope is not None
    assert targets is not None
    assert findings is not None

    assert json.loads(summary["text"])["name"] == engagement.name
    assert json.loads(scope["text"])[0]["pattern"] == "*.lab.test"
    assert json.loads(targets["text"])[0]["value"] == "app.lab.test"
    assert json.loads(findings["text"])[0]["title"] == "Open redirect"


async def test_server_resource_handlers_list_and_read(container, monkeypatch) -> None:
    engagement = await _engagement(container)
    await container.scope.add_entry(engagement.id, "*.lab.test")
    monkeypatch.setenv("KESTREL_ENGAGEMENT", engagement.name)

    server = RedTeamMCPServer(Settings.build(edition="pro"), container=container)
    mcp = server.build()

    list_handler = mcp.request_handlers[ListResourcesRequest]
    read_handler = mcp.request_handlers[ReadResourceRequest]

    listed = await list_handler(ListResourcesRequest())
    payload = await read_handler(
        ReadResourceRequest(params={"uri": f"engagement://{engagement.id}/scope"})
    )

    assert len(listed.root.resources) == 4
    assert str(listed.root.resources[0].uri).startswith("engagement://")
    assert "*.lab.test" in payload.root.contents[0].text
