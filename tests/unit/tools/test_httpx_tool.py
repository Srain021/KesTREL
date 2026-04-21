from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult, ToolNotFoundError
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.httpx_tool import HttpxModule, _parse_httpx_jsonl

pytestmark = pytest.mark.asyncio


def _module(scope: list[str] | None = None) -> HttpxModule:
    settings = Settings()
    settings.tools.httpx.enabled = True
    settings.tools.httpx.binary = "httpx"
    return HttpxModule(settings, ScopeGuard(scope or ["*.example.com"]))


def _spec(module: HttpxModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_httpx_probe_parses_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        assert kwargs["stdin_data"] == b"www.example.com\napi.example.com\n"
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout=(
                '{"input":"www.example.com","url":"https://www.example.com",'
                '"status-code":200,"title":"Home","tech":["nginx"]}\n'
                "noise\n"
                '{"input":"api.example.com","url":"https://api.example.com","status-code":403}\n'
            ),
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.httpx_tool.resolve_binary", lambda *_: "httpx")
    monkeypatch.setattr("kestrel_mcp.tools.httpx_tool.run_command", fake_run_command)

    result = await _spec(_module(), "httpx_probe").handler(
        {"targets": ["www.example.com", "api.example.com"]}
    )

    assert not result.is_error
    assert result.structured["count"] == 2
    assert result.structured["probes"][0]["status_code"] == 200
    assert result.structured["probes"][0]["tech"] == ["nginx"]


async def test_httpx_probe_returns_error_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ToolNotFoundError("httpx missing")

    monkeypatch.setattr("kestrel_mcp.tools.httpx_tool.resolve_binary", missing)

    result = await _spec(_module(), "httpx_probe").handler({"targets": ["www.example.com"]})

    assert result.is_error
    assert "httpx missing" in result.text


async def test_httpx_probe_refuses_out_of_scope_target() -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(["*.example.com"]), "httpx_probe").handler(
            {"targets": ["evil.test"]}
        )


async def test_httpx_version_uses_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout="httpx v1.6.0\n",
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.httpx_tool.resolve_binary", lambda *_: "httpx")
    monkeypatch.setattr("kestrel_mcp.tools.httpx_tool.run_command", fake_run_command)

    result = await _spec(_module(), "httpx_version").handler({})

    assert not result.is_error
    assert "v1.6.0" in result.text


async def test_parse_httpx_jsonl_skips_noise() -> None:
    assert _parse_httpx_jsonl('{"url":"https://a.example.com"}\nnoise\n') == [
        {
            "target": "https://a.example.com",
            "url": "https://a.example.com",
            "status_code": None,
            "title": None,
            "tech": [],
        }
    ]
