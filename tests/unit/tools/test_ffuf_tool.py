from __future__ import annotations

from pathlib import Path

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult, ToolNotFoundError
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.ffuf_tool import FfufModule, _parse_ffuf_json

pytestmark = pytest.mark.asyncio


def _module(wordlists_dir: Path, scope: list[str] | None = None) -> FfufModule:
    settings = Settings(
        tools={
            "ffuf": {
                "enabled": True,
                "binary": "ffuf",
                "wordlists_dir": str(wordlists_dir),
            }
        }
    )
    return FfufModule(settings, ScopeGuard(scope or ["*.example.com"]))


def _spec(module: FfufModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_ffuf_dir_bruteforce_parses_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "words.txt").write_text("admin\n", encoding="utf-8")

    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        assert "https://app.example.com/FUZZ" in argv
        assert str(tmp_path / "words.txt") in argv
        return ExecutionResult(
            argv=argv,
            exit_code=0,
            stdout='{"results":[{"url":"https://app.example.com/admin","status":200}]}',
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.ffuf_tool.resolve_binary", lambda *_: "ffuf")
    monkeypatch.setattr("kestrel_mcp.tools.ffuf_tool.run_command", fake_run_command)

    result = await _spec(_module(tmp_path), "ffuf_dir_bruteforce").handler(
        {"url": "https://app.example.com", "wordlist": "words.txt"}
    )

    assert not result.is_error
    assert result.structured["results"][0]["status"] == 200


async def test_ffuf_returns_error_when_binary_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ToolNotFoundError("ffuf missing")

    monkeypatch.setattr("kestrel_mcp.tools.ffuf_tool.resolve_binary", missing)
    result = await _spec(_module(tmp_path), "ffuf_dir_bruteforce").handler(
        {"url": "https://app.example.com", "wordlist": "words.txt"}
    )

    assert result.is_error
    assert "ffuf missing" in result.text


async def test_ffuf_refuses_out_of_scope_url(tmp_path: Path) -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(tmp_path), "ffuf_dir_bruteforce").handler(
            {"url": "https://evil.test", "wordlist": "words.txt"}
        )


async def test_ffuf_refuses_wordlist_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("kestrel_mcp.tools.ffuf_tool.resolve_binary", lambda *_: "ffuf")
    result = await _spec(_module(tmp_path), "ffuf_param_fuzz").handler(
        {"url": "https://app.example.com/search", "wordlist": "../secret.txt"}
    )

    assert result.is_error
    assert "escapes base" in result.text


async def test_ffuf_version_and_registry_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=0,
            stdout="ffuf version 2.1.0\n",
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.ffuf_tool.resolve_binary", lambda *_: "ffuf")
    monkeypatch.setattr("kestrel_mcp.tools.ffuf_tool.run_command", fake_run_command)

    module = _module(tmp_path)
    version = await _spec(module, "ffuf_version").handler({})

    assert version.text == "ffuf version 2.1.0"

    from kestrel_mcp.tools import load_modules

    ids = {m.id for m in load_modules(module.settings, ScopeGuard(["*.example.com"]))}
    assert "ffuf" in ids


async def test_parse_ffuf_json_empty() -> None:
    assert _parse_ffuf_json("not json") == []
