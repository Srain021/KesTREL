"""FastAPI app skeleton smoke tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from redteam_mcp.core import ServiceContainer
from redteam_mcp.domain import entities as ent
from redteam_mcp.webui import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


@pytest.fixture
async def client(container):
    app = create_app(container)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_root_ok(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Dashboard" in response.text
    assert "kestrel-mcp" in response.text


async def test_engagements_empty(client):
    response = await client.get("/api/v1/engagements")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "engagements": []}


async def test_engagements_list_created(container, client):
    engagement = await container.engagement.create(
        name="web-one",
        display_name="Web One",
        engagement_type=ent.EngagementType.CTF,
        client="Acme",
    )

    response = await client.get("/api/v1/engagements")

    assert response.status_code == 200
    assert response.json() == {
        "count": 1,
        "engagements": [
            {
                "id": str(engagement.id),
                "name": "web-one",
                "status": "planning",
            }
        ],
    }


async def test_docs_route_enabled(client):
    response = await client.get("/__docs")
    assert response.status_code == 200
