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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        yield http
    await c.dispose()


async def test_settings_page_renders(client):
    r = await client.get("/settings")
    assert r.status_code == 200
    assert "Settings" in r.text
    assert "Tool" in r.text


async def test_settings_page_shows_environment(client):
    r = await client.get("/settings")
    assert "kestrel-mcp" in r.text
    assert "Authorized scope" in r.text


async def test_settings_masks_shodan_key(client, monkeypatch):
    secret = "V8LdA4Fxi-secret-value"
    monkeypatch.setenv("SHODAN_API_KEY", secret)
    r = await client.get("/settings")
    assert r.status_code == 200
    assert "present" in r.text
    assert secret not in r.text
