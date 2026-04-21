from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.executor import ExecutionResult, ToolNotFoundError
from kestrel_mcp.security import AuthorizationError, ScopeGuard
from kestrel_mcp.tools.nmap_tool import NmapModule, parse_nmap_xml

pytestmark = pytest.mark.asyncio

NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="10.0.0.5" addrtype="ipv4"/>
    <hostnames><hostname name="web.lab"/></hostnames>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="nginx" version="1.24"/>
      </port>
    </ports>
    <os><osmatch name="Linux 5.x" accuracy="95"/></os>
  </host>
</nmaprun>
"""


def _module(scope: list[str] | None = None) -> NmapModule:
    settings = Settings()
    settings.tools.nmap.enabled = True
    settings.tools.nmap.binary = "nmap"
    return NmapModule(settings, ScopeGuard(scope or ["10.0.0.0/8"]))


def _spec(module: NmapModule, name: str):
    return next(s for s in module.specs() if s.name == name)


async def test_nmap_scan_parses_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        assert "-oX" in argv
        assert "10.0.0.5" in argv
        return ExecutionResult(argv=argv, exit_code=0, stdout=NMAP_XML, stderr="", duration_sec=0.1)

    monkeypatch.setattr("kestrel_mcp.tools.nmap_tool.resolve_binary", lambda *_: "nmap")
    monkeypatch.setattr("kestrel_mcp.tools.nmap_tool.run_command", fake_run_command)

    result = await _spec(_module(), "nmap_scan").handler(
        {"targets": ["10.0.0.5"], "ports": "80", "timing": 3}
    )

    assert not result.is_error
    host = result.structured["hosts"][0]
    assert host["address"] == "10.0.0.5"
    assert host["ports"][0]["service"] == "http"


async def test_nmap_scan_returns_error_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ToolNotFoundError("nmap missing")

    monkeypatch.setattr("kestrel_mcp.tools.nmap_tool.resolve_binary", missing)

    result = await _spec(_module(), "nmap_scan").handler({"targets": ["10.0.0.5"]})

    assert result.is_error
    assert "nmap missing" in result.text


async def test_nmap_scan_refuses_out_of_scope_target() -> None:
    with pytest.raises(AuthorizationError):
        await _spec(_module(["10.0.0.0/8"]), "nmap_scan").handler({"targets": ["192.0.2.10"]})


async def test_nmap_os_detect_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_command(*args, **kwargs):  # noqa: ANN002, ANN003
        argv = list(args[0])
        stdout = "Nmap version 7.95\n" if "--version" in argv else NMAP_XML
        return ExecutionResult(argv=argv, exit_code=0, stdout=stdout, stderr="", duration_sec=0.1)

    monkeypatch.setattr("kestrel_mcp.tools.nmap_tool.resolve_binary", lambda *_: "nmap")
    monkeypatch.setattr("kestrel_mcp.tools.nmap_tool.run_command", fake_run_command)

    module = _module()
    os_result = await _spec(module, "nmap_os_detect").handler({"target": "10.0.0.5"})
    version = await _spec(module, "nmap_version").handler({})

    assert os_result.structured["hosts"][0]["osmatches"][0]["name"] == "Linux 5.x"
    assert version.text == "Nmap version 7.95"


async def test_parse_nmap_xml_empty() -> None:
    assert parse_nmap_xml("") == {"hosts": []}
