from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.katana_tool import KatanaModule, _parse_katana_jsonl

pytestmark = pytest.mark.asyncio


def _module() -> KatanaModule:
    return KatanaModule(Settings(tools={"katana": {"enabled": True, "binary": "katana"}}), ScopeGuard(["*.example.com"]))


def _spec(module: KatanaModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_katana_crawl_returns_interesting_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        assert kwargs["stdin_data"] == b"https://app.example.com\n"
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout='{"url":"https://app.example.com/admin","method":"GET","status_code":200}\n',
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.katana_tool.resolve_binary", lambda *_: "katana")
    monkeypatch.setattr("kestrel_mcp.tools.katana_tool.run_command", fake_run_command)
    result = await _spec(_module(), "katana_crawl").handler({"targets": ["https://app.example.com"]})

    assert not result.is_error
    assert result.structured["urls"][0]["interesting"] is True


async def test_katana_refuses_out_of_scope() -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(), "katana_crawl").handler({"targets": ["https://evil.test"]})


async def test_parse_katana_jsonl_skips_bad_lines() -> None:
    assert _parse_katana_jsonl("bad\n{}") == []
