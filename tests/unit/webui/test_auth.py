from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient, BasicAuth

from redteam_mcp.config import Settings, WebUISettings
from redteam_mcp.core import ServiceContainer
from redteam_mcp.webui import create_app


@asynccontextmanager
async def _client(settings: Settings) -> AsyncIterator[AsyncClient]:
    c = ServiceContainer.in_memory()
    await c.initialise()
    app = create_app(c, settings=settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield client
    await c.dispose()


@pytest.mark.parametrize("path", ["/", "/settings", "/api/v1/engagements"])
async def test_auth_required_blocks_existing_routes(path, monkeypatch):
    monkeypatch.setenv("KESTREL_WEB_PASS", "secret")
    async with _client(Settings(webui=WebUISettings(auth_required=True))) as client:
        r = await client.get(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Basic"


async def test_auth_required_allows_valid_basic_credentials(monkeypatch):
    monkeypatch.setenv("KESTREL_WEB_USER", "operator")
    monkeypatch.setenv("KESTREL_WEB_PASS", "secret")
    settings = Settings(webui=WebUISettings(auth_required=True))
    async with _client(settings) as client:
        r = await client.get("/", auth=BasicAuth("operator", "secret"))
    assert r.status_code == 200
    assert "kestrel-mcp" in r.text


async def test_auth_required_rejects_wrong_credentials(monkeypatch):
    monkeypatch.setenv("KESTREL_WEB_PASS", "secret")
    settings = Settings(webui=WebUISettings(auth_required=True))
    async with _client(settings) as client:
        r = await client.get("/", auth=BasicAuth("kestrel", "wrong"))
    assert r.status_code == 401


async def test_auth_disabled_by_default_allows_anonymous():
    async with _client(Settings()) as client:
        r = await client.get("/")
    assert r.status_code == 200
