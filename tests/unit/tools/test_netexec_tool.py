from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.netexec_tool import NetExecModule, _parse_kerberoast_hashes, _parse_nxc_auth

pytestmark = pytest.mark.asyncio


def _module() -> NetExecModule:
    return NetExecModule(
        Settings(tools={"netexec": {"enabled": True, "binary": "nxc"}}), ScopeGuard(["10.0.0.0/8"])
    )


def _spec(module: NetExecModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_netexec_auth_redacts_input_password_but_returns_detailed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        assert "-p" in argv
        return ExecutionResult(
            argv=argv,
            exit_code=0,
            stdout="SMB 10.0.0.5 445 HOST [+] LAB\\alice:secret (Pwn3d!)",
            stderr="",
            duration_sec=0.1,
        )

    monkeypatch.setattr("kestrel_mcp.tools.netexec_tool.resolve_binary", lambda *_: "nxc")
    monkeypatch.setattr("kestrel_mcp.tools.netexec_tool.run_command", fake_run_command)
    result = await _spec(_module(), "netexec_smb_auth").handler(
        {"targets": ["10.0.0.5"], "domain": "LAB", "username": "alice", "password": "secret"}
    )

    assert not result.is_error
    assert result.structured["auth_results"][0]["admin"] is True
    assert "secret" not in result.structured["stdout"]
    assert result.structured["output_lines"]


async def test_netexec_auth_requires_single_secret_source() -> None:
    result = await _spec(_module(), "netexec_smb_auth").handler(
        {"targets": ["10.0.0.5"], "username": "alice", "password": "secret", "ntlm_hash": "0" * 32}
    )
    assert result.is_error


async def test_netexec_kerberoast_returns_hash_details(monkeypatch: pytest.MonkeyPatch) -> None:
    krb = "$krb5tgs$23$*svc$LAB.LOCAL$MSSQLSvc/sql.lab.local:1433*$abcdef"

    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        return ExecutionResult(
            argv=list(args[0]), exit_code=0, stdout=f"{krb}\n", stderr="", duration_sec=0.1
        )

    monkeypatch.setattr("kestrel_mcp.tools.netexec_tool.resolve_binary", lambda *_: "nxc")
    monkeypatch.setattr("kestrel_mcp.tools.netexec_tool.run_command", fake_run_command)
    result = await _spec(_module(), "netexec_ldap_kerberoast").handler(
        {"target": "10.0.0.5", "domain": "LAB", "username": "alice", "password": "secret"}
    )

    assert not result.is_error
    assert result.structured["kerberoast_hashes"][0]["hash"] == krb


async def test_netexec_refuses_out_of_scope() -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(), "netexec_smb_auth").handler(
            {"targets": ["192.0.2.5"], "username": "a", "password": "b"}
        )


async def test_netexec_parsers() -> None:
    assert _parse_nxc_auth("SMB 10.0.0.5 [+] user (Pwn3d!)")[0]["success"] is True
    assert _parse_kerberoast_hashes("$krb5tgs$23$*svc$x$y$z") == ["$krb5tgs$23$*svc$x$y$z"]
