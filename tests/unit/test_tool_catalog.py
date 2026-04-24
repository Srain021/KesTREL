from __future__ import annotations

import json

from kestrel_mcp.__main__ import _edition_state, list_tools_cmd
from kestrel_mcp.config import Settings
from kestrel_mcp.tool_catalog import advertised_specs
from kestrel_mcp.tools.base import ToolResult, ToolSpec


async def _handler(_args):
    return ToolResult(text="ok")


def _spec(name: str, *, tags: list[str] | None = None) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} short description.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_handler,
        tags=tags or [],
        when_to_use=["Use this when the target and authorization are clear."],
        when_not_to_use=["Do not use it for broad unauthorised scans."],
        prerequisites=["An active engagement exists."],
        follow_ups=["Summarise the result and choose the next narrow step."],
        pitfalls=["Do not fabricate optional arguments just to fill the schema."],
        local_model_hints="Prefer the HARNESS tools when uncertain.",
    )


def test_compact_description_is_smaller_than_full() -> None:
    spec = _spec("nuclei_scan", tags=["scan", "web"])

    compact = spec.render_compact_description()
    full = spec.render_full_description()

    assert len(compact) < len(full) / 2
    assert "=== WHEN TO USE ===" not in compact
    assert "=== WHEN TO USE ===" in full


def test_harness_first_exposes_only_management_workflow_and_reports() -> None:
    settings = Settings.build(llm={"tool_exposure": "harness_first"})
    specs = [
        _spec("target_add"),
        _spec("harness_start"),
        _spec("readiness_check", tags=["readiness"]),
        _spec("generate_report", tags=["report"]),
        _spec("recon_target", tags=["workflow"]),
        _spec("nuclei_scan", tags=["scan"]),
    ]

    visible = {spec.name for spec in advertised_specs(specs, settings)}

    assert visible == {
        "target_add",
        "harness_start",
        "readiness_check",
        "generate_report",
        "recon_target",
    }


def test_cli_list_tools_compact_harness_first_is_smaller(monkeypatch, capsys) -> None:
    _edition_state["value"] = None
    monkeypatch.setenv("KESTREL_MCP_LLM__TOOL_DESCRIPTION_MODE", "full")
    monkeypatch.setenv("KESTREL_MCP_LLM__TOOL_EXPOSURE", "all")
    list_tools_cmd()
    full = capsys.readouterr().out

    monkeypatch.setenv("KESTREL_MCP_LLM__TOOL_DESCRIPTION_MODE", "compact")
    monkeypatch.setenv("KESTREL_MCP_LLM__TOOL_EXPOSURE", "harness_first")
    monkeypatch.setenv("KESTREL_MCP_LLM__MODEL_TIER", "local")
    list_tools_cmd()
    compact = capsys.readouterr().out

    payload = json.loads(compact)
    names = {item["name"] for item in payload}
    assert len(compact) < len(full)
    assert "harness_start" in names
    assert "target_add" in names
    assert "nuclei_scan" not in names
