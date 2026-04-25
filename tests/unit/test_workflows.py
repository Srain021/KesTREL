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


async def test_web_app_deep_scan_registers_only_when_all_handlers_available() -> None:
    settings = Settings.build()
    guard = ScopeGuard(["*.example.com"])

    async def ok(arguments: dict[str, object]) -> ToolResult:
        return ToolResult(text="ok", structured={})

    incomplete = StubModule(settings, guard, specs=[_spec("httpx_probe", ok)])
    with patch("kestrel_mcp.workflows.load_modules", return_value=[incomplete]):
        specs = load_workflow_specs(settings, guard)
    assert "web_app_deep_scan" not in {spec.name for spec in specs}

    complete = StubModule(
        settings,
        guard,
        specs=[
            _spec("httpx_probe", ok),
            _spec("katana_crawl", ok),
            _spec("nuclei_scan", ok),
            _spec("sqlmap_scan", ok),
        ],
    )
    with patch("kestrel_mcp.workflows.load_modules", return_value=[complete]):
        specs = load_workflow_specs(settings, guard)
    assert "web_app_deep_scan" in {spec.name for spec in specs}


async def test_web_app_deep_scan_runs_httpx_katana_nuclei_sqlmap_order() -> None:
    settings = Settings.build()
    guard = ScopeGuard(["*.example.com"])
    calls: list[str] = []

    async def httpx(arguments: dict[str, object]) -> ToolResult:
        calls.append("httpx")
        return ToolResult(text="httpx", structured={"probes": [{"url": "https://app.example.com"}]})

    async def katana(arguments: dict[str, object]) -> ToolResult:
        calls.append("katana")
        return ToolResult(
            text="katana",
            structured={"urls": [{"url": "https://app.example.com/item?id=1"}]},
        )

    async def nuclei(arguments: dict[str, object]) -> ToolResult:
        calls.append("nuclei")
        return ToolResult(text="nuclei", structured={"findings": [{"id": "n1"}]})

    async def sqlmap(arguments: dict[str, object]) -> ToolResult:
        calls.append("sqlmap")
        return ToolResult(text="sqlmap", structured={"injectable": True, "parameter": "id"})

    module = StubModule(
        settings,
        guard,
        specs=[
            _spec("httpx_probe", httpx),
            _spec("katana_crawl", katana),
            _spec("nuclei_scan", nuclei),
            _spec("sqlmap_scan", sqlmap),
        ],
    )
    with patch("kestrel_mcp.workflows.load_modules", return_value=[module]):
        specs = load_workflow_specs(settings, guard)

    workflow = next(spec for spec in specs if spec.name == "web_app_deep_scan")
    result = await workflow.handler({"targets": ["https://app.example.com"]})

    assert calls == ["httpx", "katana", "nuclei", "sqlmap"]
    assert result.structured["sqlmap"][0]["result"]["injectable"] is True


async def test_recon_target_can_call_amass_when_requested() -> None:
    settings = Settings.build()
    guard = ScopeGuard(["example.com", "*.example.com", "10.0.0.0/8"])
    calls: list[str] = []

    async def shodan_search(arguments: dict[str, object]) -> ToolResult:
        calls.append("shodan_search")
        return ToolResult(text="search", structured={"hits": []})

    async def shodan_host(arguments: dict[str, object]) -> ToolResult:
        calls.append("shodan_host")
        return ToolResult(text="host", structured={})

    async def amass(arguments: dict[str, object]) -> ToolResult:
        calls.append("amass")
        return ToolResult(
            text="amass", structured={"ips": ["10.0.0.5"], "subdomains": ["a.example.com"]}
        )

    module = StubModule(
        settings,
        guard,
        specs=[
            _spec("shodan_search", shodan_search),
            _spec("shodan_host", shodan_host),
            _spec("amass_enum", amass),
        ],
    )
    with patch("kestrel_mcp.workflows.load_modules", return_value=[module]):
        specs = load_workflow_specs(settings, guard)

    workflow = next(spec for spec in specs if spec.name == "recon_target")
    result = await workflow.handler({"target": "example.com", "use_amass": True})

    assert "amass" in calls
    assert result.structured["amass"]["subdomains"] == ["a.example.com"]
