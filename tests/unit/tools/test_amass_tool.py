from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult, ToolNotFoundError
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.amass_tool import AmassModule, _parse_amass_json

pytestmark = pytest.mark.asyncio


def _module() -> AmassModule:
    return AmassModule(
        Settings(tools={"amass": {"enabled": True, "binary": "amass"}}),
        ScopeGuard(["example.com", "*.example.com"]),
    )


def _spec(module: AmassModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_amass_enum_parses_jsonl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout='{"name":"a.example.com","addresses":[{"ip":"10.0.0.5"}],"source":"crtsh"}\n',
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.amass_tool.resolve_binary", lambda *_: "amass")
    monkeypatch.setattr("kestrel_mcp.tools.amass_tool.run_command", fake_run_command)
    result = await _spec(_module(), "amass_enum").handler({"domain": "example.com"})

    assert not result.is_error
    assert result.structured["subdomains"] == ["a.example.com"]
    assert result.structured["ips"] == ["10.0.0.5"]


async def test_amass_missing_binary_and_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kestrel_mcp.tools.amass_tool.resolve_binary",
        lambda *_: (_ for _ in ()).throw(ToolNotFoundError("amass missing")),
    )
    result = await _spec(_module(), "amass_version").handler({})
    assert result.is_error

    with pytest.raises(AuthorizationError):
        await _spec(_module(), "amass_enum").handler({"domain": "evil.test"})


async def test_parse_amass_json_skips_noise() -> None:
    assert _parse_amass_json("noise\n{}") == []


async def test_amass_registry_loads() -> None:
    from kestrel_mcp.tools import load_modules

    ids = {m.id for m in load_modules(_module().settings, ScopeGuard(["example.com"]))}
    assert "amass" in ids
