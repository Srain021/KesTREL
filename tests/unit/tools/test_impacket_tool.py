from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.impacket_tool import ImpacketModule

pytestmark = pytest.mark.asyncio


def _module(scope: list[str] | None = None) -> ImpacketModule:
    settings = Settings(tools={"impacket": {"enabled": True}})
    return ImpacketModule(settings, ScopeGuard(scope or ["10.0.0.0/8"]))


def _spec(module: ImpacketModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_impacket_psexec_invokes_module_without_returning_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        assert argv[1:4] == ["-m", "impacket.examples.psexec", "LAB/alice:secret@10.0.0.5"]
        return ExecutionResult(argv=argv, exit_code=0, stdout="ok", stderr="", duration_sec=0.1)

    monkeypatch.setattr("kestrel_mcp.tools.impacket_tool.run_command", fake_run_command)

    result = await _spec(_module(), "impacket_psexec").handler(
        {
            "target": "10.0.0.5",
            "domain": "LAB",
            "username": "alice",
            "password": "secret",
            "command": "whoami",
        }
    )

    assert not result.is_error
    assert "secret" not in result.structured
    assert "argv" not in result.structured


async def test_impacket_nonzero_exit_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]),
            exit_code=1,
            stdout="",
            stderr="auth failed",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.impacket_tool.run_command", fake_run_command)

    result = await _spec(_module(), "impacket_secretsdump").handler(
        {"target": "10.0.0.5", "username": "alice", "password": "bad"}
    )

    assert result.is_error
    assert result.structured["stderr_tail"] == "auth failed"


async def test_impacket_refuses_out_of_scope_target() -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(["10.0.0.0/8"]), "impacket_wmiexec").handler(
            {"target": "192.0.2.20", "username": "alice", "password": "secret"}
        )


async def test_impacket_get_user_spns_and_registry_load(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        assert "impacket.examples.GetUserSPNs" in argv
        assert "-dc-ip" in argv
        return ExecutionResult(argv=argv, exit_code=0, stdout="spn", stderr="", duration_sec=0.1)

    monkeypatch.setattr("kestrel_mcp.tools.impacket_tool.run_command", fake_run_command)

    module = _module()
    result = await _spec(module, "impacket_get_user_spns").handler(
        {"target": "10.0.0.5", "domain": "LAB", "username": "alice", "password": "secret"}
    )
    assert not result.is_error

    from kestrel_mcp.tools import load_modules

    ids = {m.id for m in load_modules(module.settings, ScopeGuard(["10.0.0.0/8"]))}
    assert "impacket" in ids
