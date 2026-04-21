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


async def test_impacket_tools_have_complete_guidance():
    """Every Impacket ToolSpec (all dangerous) must ship full guidance + param descriptions.

    This is a regression guard: adding a new Impacket tool without guidance
    will fail this test. Re-enable fields as coverage grows across B05b-f.
    """

    from kestrel_mcp.config import Settings
    from kestrel_mcp.security import ScopeGuard
    from kestrel_mcp.tools.impacket_tool import ImpacketModule

    module = ImpacketModule(Settings(), ScopeGuard([]))
    specs = module.specs()
    assert len(specs) == 5, "Impacket module ships exactly 5 tools today."

    required_nonempty = (
        "when_to_use",
        "when_not_to_use",
        "prerequisites",
        "follow_ups",
        "pitfalls",
    )
    for spec in specs:
        assert spec.dangerous, f"{spec.name}: all Impacket tools must stay dangerous=True."
        for field_name in required_nonempty:
            value = getattr(spec, field_name)
            assert value, (
                f"{spec.name}: guidance field '{field_name}' is empty. "
                "Every high-risk Impacket ToolSpec must populate it (see RFC-B05a)."
            )
        assert spec.local_model_hints, (
            f"{spec.name}: local_model_hints is None. "
            "Dangerous tools must carry an explicit weak-model hint (RFC-B05a)."
        )

        props = spec.input_schema.get("properties", {})
        assert props, f"{spec.name}: input_schema has no properties."
        for prop_name, prop_def in props.items():
            assert "description" in prop_def and prop_def["description"].strip(), (
                f"{spec.name}: property '{prop_name}' is missing a description "
                "(RFC-B05a requires every param to be self-documenting)."
            )
