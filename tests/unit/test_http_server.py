from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from kestrel_mcp.config import Settings
from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.http_server import create_http_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


async def test_http_healthz_reports_transport(container) -> None:
    app = create_http_app(Settings.build(edition="team"), container=container, token="secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/__healthz")

    assert response.status_code == 200
    assert response.json()["transport"] == "streamable-http"
    assert response.json()["edition"] == "team"


async def test_http_mcp_requires_bearer_token(container) -> None:
    app = create_http_app(Settings.build(edition="team"), container=container, token="secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_http_mcp_rejects_wrong_bearer_token(container) -> None:
    app = create_http_app(Settings.build(edition="team"), container=container, token="secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post(
            "/mcp",
            headers={"Authorization": "Bearer wrong"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )

    assert response.status_code == 401
