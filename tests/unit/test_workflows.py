from __future__ import annotations

from unittest.mock import patch

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.base import ToolModule, ToolResult, ToolSpec
from kestrel_mcp.workflows import load_workflow_specs

pytestmark = pytest.mark.asyncio


class StubModule(ToolModule):
    id = "stub"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard, specs: list[ToolSpec]) -> None:
        super().__init__(settings, scope_guard)
        self._specs = specs

    def specs(self) -> list[ToolSpec]:
        return list(self._specs)


def _spec(name: str, handler) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=name,
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        },
        handler=handler,
    )


async def test_exploit_chain_uses_sliver_generate_implant_handler() -> None:
    settings = Settings.build()
    guard = ScopeGuard(["*.example.com"])
    calls: list[dict[str, object]] = []

    async def sliver_handler(arguments: dict[str, object]) -> ToolResult:
        calls.append(arguments)
        return ToolResult(text="generated", structured={"artifact": "implant.exe"})

    module = StubModule(
        settings,
        guard,
        specs=[_spec("sliver_generate_implant", sliver_handler)],
    )

    with patch("kestrel_mcp.workflows.load_modules", return_value=[module]):
        specs = load_workflow_specs(settings, guard)

    exploit = next(spec for spec in specs if spec.name == "exploit_chain")
    result = await exploit.handler(
        {
            "target": "app.example.com",
            "finding": {"category": "misconfiguration"},
            "acknowledge_risk": True,
            "protocol": "mtls",
            "callback_addr": "c2.example.com:443",
        }
    )

    assert calls == [
        {
            "protocol": "mtls",
            "callback_addr": "c2.example.com:443",
            "os": "windows",
            "arch": "amd64",
            "format": "exe",
        }
    ]
    assert result.structured is not None
    assert result.structured["generated"]["sliver"]["artifact"] == "implant.exe"


async def test_exploit_chain_parses_deprecated_listener_url_alias() -> None:
    settings = Settings.build()
    guard = ScopeGuard(["*.example.com"])
    calls: list[dict[str, object]] = []

    async def sliver_handler(arguments: dict[str, object]) -> ToolResult:
        calls.append(arguments)
        return ToolResult(text="generated", structured={"artifact": "implant.dylib"})

    module = StubModule(
        settings,
        guard,
        specs=[_spec("sliver_generate_implant", sliver_handler)],
    )

    with patch("kestrel_mcp.workflows.load_modules", return_value=[module]):
        specs = load_workflow_specs(settings, guard)

    exploit = next(spec for spec in specs if spec.name == "exploit_chain")
    await exploit.handler(
        {
            "target": "app.example.com",
            "finding": {"category": "vulnerable_component"},
            "acknowledge_risk": True,
            "os": "macos",
            "listener_url": "mtls://c2.example.com:443",
        }
    )

    assert calls == [
        {
            "protocol": "mtls",
            "callback_addr": "c2.example.com:443",
            "os": "darwin",
            "arch": "amd64",
            "format": "exe",
        }
    ]
