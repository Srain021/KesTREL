from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.sqlmap_tool import SqlmapModule, _parse_sqlmap_stdout

pytestmark = pytest.mark.asyncio


def _module(tmp_path) -> SqlmapModule:
    return SqlmapModule(
        Settings(
            tools={"sqlmap": {"enabled": True, "binary": "sqlmap", "output_dir": str(tmp_path)}}
        ),
        ScopeGuard(["*.example.com"]),
    )


def _spec(module: SqlmapModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_sqlmap_scan_detects_injection(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        assert "--batch" in argv
        return ExecutionResult(
            argv=argv,
            exit_code=0,
            stdout="Parameter: id (GET)\nType: boolean-based blind\nback-end DBMS: MySQL\nis vulnerable",
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.sqlmap_tool.resolve_binary", lambda *_: "sqlmap")
    monkeypatch.setattr("kestrel_mcp.tools.sqlmap_tool.run_command", fake_run_command)
    result = await _spec(_module(tmp_path), "sqlmap_scan").handler(
        {"url": "https://app.example.com/item?id=1"}
    )

    assert not result.is_error
    assert result.structured["injectable"] is True
    assert result.structured["parameter"] == "id (GET)"


async def test_sqlmap_dump_requires_ack(tmp_path) -> None:
    result = await _spec(_module(tmp_path), "sqlmap_dump_table").handler(
        {
            "url": "https://app.example.com/item?id=1",
            "database": "app",
            "table": "users",
            "acknowledge_risk": False,
        }
    )
    assert result.is_error


async def test_sqlmap_refuses_out_of_scope(tmp_path) -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(tmp_path), "sqlmap_scan").handler({"url": "https://evil.test"})


async def test_parse_sqlmap_stdout_empty() -> None:
    assert _parse_sqlmap_stdout("nothing")["injectable"] is False
