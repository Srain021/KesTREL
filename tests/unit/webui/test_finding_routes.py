from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.webui import create_app


@pytest.fixture
async def setup():
    c = ServiceContainer.in_memory()
    await c.initialise()
    engagement = await c.engagement.create(
        name="finding-test",
        display_name="Finding Test",
        engagement_type=ent.EngagementType.CTF,
        client="Demo",
    )
    target_id = uuid4()
    findings = [
        await c.finding.create(
            engagement_id=engagement.id,
            target_id=target_id,
            title="Critical RCE",
            severity=ent.FindingSeverity.CRITICAL,
            discovered_by_tool="nuclei",
        ),
        await c.finding.create(
            engagement_id=engagement.id,
            target_id=target_id,
            title="High SSRF",
            severity=ent.FindingSeverity.HIGH,
            discovered_by_tool="manual",
        ),
        await c.finding.create(
            engagement_id=engagement.id,
            target_id=target_id,
            title="Info banner",
            severity=ent.FindingSeverity.INFO,
            discovered_by_tool="httpx",
        ),
    ]
    app = create_app(c)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield client, c, findings
    await c.dispose()


async def test_list_findings(setup):
    client, _, _ = setup
    r = await client.get("/engagements/finding-test/findings")
    assert r.status_code == 200
    assert "Critical RCE" in r.text
    assert "High SSRF" in r.text
    assert "Info banner" in r.text


async def test_filter_by_severity(setup):
    client, _, _ = setup
    r = await client.get("/engagements/finding-test/findings?severity=critical")
    assert r.status_code == 200
    assert "Critical RCE" in r.text
    assert "High SSRF" not in r.text


async def test_transition_finding(setup):
    client, c, findings = setup
    r = await client.post(
        f"/engagements/finding-test/findings/{findings[0].id}/transition",
        data={"status": "triaged"},
    )
    assert r.status_code == 200
    assert "triaged" in r.text
    updated = await c.finding.get(findings[0].id)
    assert updated is not None
    assert updated.status == ent.FindingStatus.TRIAGED


async def test_invalid_transition_409(setup):
    client, _, findings = setup
    r = await client.post(
        f"/engagements/finding-test/findings/{findings[0].id}/transition",
        data={"status": "fixed"},
    )
    assert r.status_code == 409


async def test_missing_engagement_404(setup):
    client, _, _ = setup
    r = await client.get("/engagements/nope/findings")
    assert r.status_code == 404
