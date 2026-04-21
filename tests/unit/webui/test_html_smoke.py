from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from redteam_mcp.core import ServiceContainer
from redteam_mcp.webui import create_app


@pytest.fixture
async def client():
    c = ServiceContainer.in_memory()
    await c.initialise()
    app = create_app(c)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        yield cl
    await c.dispose()


async def test_root_html(client):
    r = await client.get("/")
    assert r.status_code == 200
    text = r.text
    assert "<!doctype html>" in text.lower()
    assert "kestrel-mcp" in text
    assert "htmx.org" in text
    assert "tailwindcss" in text


async def test_healthz(client):
    r = await client.get("/__healthz")
    assert r.json() == {"ok": True}


async def test_engagements_nav_present(client):
    r = await client.get("/")
    assert "/engagements" in r.text
    assert "/tools" in r.text
