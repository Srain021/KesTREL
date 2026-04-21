from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from redteam_mcp.core import ServiceContainer
from redteam_mcp.domain import entities as ent
from redteam_mcp.webui import create_app


@pytest.fixture
async def setup():
    c = ServiceContainer.in_memory()
    await c.initialise()
    app = create_app(c)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield client, c
    await c.dispose()


async def test_list_empty(setup):
    client, _ = setup
    r = await client.get("/engagements/")
    assert r.status_code == 200
    assert "Engagements" in r.text
    assert "New engagement" in r.text


async def test_create_engagement(setup):
    client, _ = setup
    r = await client.post(
        "/engagements/",
        data={
            "name": "web-test",
            "display_name": "Web Test",
            "engagement_type": "ctf",
            "client": "Demo",
        },
    )
    assert r.status_code == 200
    assert "web-test" in r.text
    assert "planning" in r.text


async def test_create_duplicate_409(setup):
    client, c = setup
    await c.engagement.create(
        name="dup",
        display_name="x",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    r = await client.post(
        "/engagements/",
        data={
            "name": "dup",
            "display_name": "x",
            "engagement_type": "ctf",
            "client": "c",
        },
    )
    assert r.status_code == 409


async def test_show_page(setup):
    client, c = setup
    await c.engagement.create(
        name="detail-test",
        display_name="Detail Test",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    r = await client.get("/engagements/detail-test")
    assert r.status_code == 200
    assert "Detail Test" in r.text
    assert "Scope entries" in r.text


async def test_show_404(setup):
    client, _ = setup
    r = await client.get("/engagements/nope")
    assert r.status_code == 404
