from __future__ import annotations

from typing import Any

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.bloodhound_tool import BloodHoundModule

pytestmark = pytest.mark.asyncio


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    requests: list[tuple[str, str, dict[str, Any] | None]] = []
    next_response = FakeResponse({"data": []})

    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.headers = kwargs.get("headers") or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):  # noqa: ANN002
        return None

    async def request(self, method: str, path: str, json=None):  # noqa: ANN001
        self.requests.append((method, path, json))
        return self.next_response


def _module() -> BloodHoundModule:
    settings = Settings(
        tools={
            "bloodhound": {
                "enabled": True,
                "api_url": "http://bloodhound.local",
                "api_key": "token",
            }
        }
    )
    return BloodHoundModule(settings, ScopeGuard([]))


def _spec(module: BloodHoundModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_bloodhound_query_posts_cypher(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.requests = []
    FakeClient.next_response = FakeResponse({"data": [{"name": "Domain Admins"}]})
    monkeypatch.setattr("kestrel_mcp.tools.bloodhound_tool.httpx.AsyncClient", FakeClient)

    result = await _spec(_module(), "bloodhound_query").handler(
        {"cypher": "MATCH (n) RETURN n", "engagement_id": "eng-1"}
    )

    assert not result.is_error
    assert result.text.endswith("1 row(s).")
    assert FakeClient.requests == [
        ("POST", "/api/v2/graphs/cypher", {"query": "MATCH (n) RETURN n", "engagement_id": "eng-1"})
    ]


async def test_bloodhound_list_datasets(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.requests = []
    FakeClient.next_response = FakeResponse({"graphs": [{"id": "g1"}, {"id": "g2"}]})
    monkeypatch.setattr("kestrel_mcp.tools.bloodhound_tool.httpx.AsyncClient", FakeClient)

    result = await _spec(_module(), "bloodhound_list_datasets").handler({})

    assert not result.is_error
    assert result.text == "BloodHound returned 2 dataset(s)."
    assert FakeClient.requests[0][1] == "/api/v2/graphs"


async def test_bloodhound_http_error_is_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeClient.next_response = FakeResponse({"error": "nope"}, status_code=500)
    monkeypatch.setattr("kestrel_mcp.tools.bloodhound_tool.httpx.AsyncClient", FakeClient)

    result = await _spec(_module(), "bloodhound_version").handler({})

    assert result.is_error
    assert "BloodHound API request failed" in result.text


async def test_bloodhound_registry_loads() -> None:
    from kestrel_mcp.tools import load_modules

    module = _module()
    ids = {m.id for m in load_modules(module.settings, ScopeGuard([]))}
    assert "bloodhound" in ids
