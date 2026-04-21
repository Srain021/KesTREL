from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult, ToolNotFoundError
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.subfinder_tool import SubfinderModule, _parse_subfinder_jsonl

pytestmark = pytest.mark.asyncio


def _module(scope: list[str] | None = None) -> SubfinderModule:
    settings = Settings()
    settings.tools.subfinder.enabled = True
    settings.tools.subfinder.binary = "subfinder"
    return SubfinderModule(settings, ScopeGuard(scope or ["example.com"]))


def _spec(module: SubfinderModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_subfinder_enum_parses_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout=(
                '{"host":"www.example.com","input":"example.com","source":"crtsh"}\n'
                "not-json\n"
                '{"host":"api.example.com","input":"example.com","source":"alienvault"}\n'
            ),
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.subfinder_tool.resolve_binary", lambda *_: "subfinder")
    monkeypatch.setattr("kestrel_mcp.tools.subfinder_tool.run_command", fake_run_command)

    result = await _spec(_module(), "subfinder_enum").handler({"domain": "example.com"})

    assert not result.is_error
    assert result.structured["count"] == 2
    assert result.structured["subdomains"] == ["api.example.com", "www.example.com"]


async def test_subfinder_enum_returns_error_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ToolNotFoundError("subfinder missing")

    monkeypatch.setattr("kestrel_mcp.tools.subfinder_tool.resolve_binary", missing)

    result = await _spec(_module(), "subfinder_enum").handler({"domain": "example.com"})

    assert result.is_error
    assert "subfinder missing" in result.text


async def test_subfinder_enum_refuses_out_of_scope_domain() -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(["example.com"]), "subfinder_enum").handler({"domain": "evil.com"})


async def test_subfinder_version_uses_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout="subfinder v2.6.6\n",
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.subfinder_tool.resolve_binary", lambda *_: "subfinder")
    monkeypatch.setattr("kestrel_mcp.tools.subfinder_tool.run_command", fake_run_command)

    result = await _spec(_module(), "subfinder_version").handler({})

    assert not result.is_error
    assert "v2.6.6" in result.text


async def test_parse_subfinder_jsonl_skips_noise() -> None:
    assert _parse_subfinder_jsonl('{"subdomain":"a.example.com"}\nnoise\n') == [
        {"host": "a.example.com", "input": None, "source": None}
    ]
