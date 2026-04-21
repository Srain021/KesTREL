"""Tests for the Sliver tool module.

Regression guard for RFC-B05b1/B05b2 guidance completeness across all
Sliver ToolSpecs. Handler-level tests live outside these RFCs' scope.
"""

from __future__ import annotations

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.base import ToolSpec
from kestrel_mcp.tools.sliver_tool import SliverModule


def _specs_by_name() -> dict[str, ToolSpec]:
    module = SliverModule(Settings(), ScopeGuard([]))
    return {spec.name: spec for spec in module.specs()}


SLIVER_TOOLS = (
    "sliver_start_server",
    "sliver_stop_server",
    "sliver_server_status",
    "sliver_run_command",
    "sliver_list_sessions",
    "sliver_list_listeners",
    "sliver_generate_implant",
    "sliver_execute_in_session",
)


async def test_sliver_tools_exist():
    specs = _specs_by_name()
    for name in SLIVER_TOOLS:
        assert name in specs, f"{name} missing from SliverModule.specs()"


async def test_sliver_dangerous_tools_carry_full_guidance():
    """Dangerous tools get ALL guidance fields populated (RFC-B05b1/B05b2).

    Non-dangerous inventory/status tools have looser requirements.
    """

    specs = _specs_by_name()
    dangerous_names = {
        "sliver_start_server",
        "sliver_run_command",
        "sliver_generate_implant",
        "sliver_execute_in_session",
    }
    required = (
        "when_to_use",
        "when_not_to_use",
        "prerequisites",
        "follow_ups",
        "pitfalls",
    )
    for name in dangerous_names:
        spec = specs[name]
        assert spec.dangerous, f"{name}: expected dangerous=True."
        for field_name in required:
            assert getattr(spec, field_name), (
                f"{name}: guidance field '{field_name}' is empty (RFC-B05b)."
            )
        assert spec.local_model_hints, f"{name}: local_model_hints missing."
        assert spec.example_conversation, (
            f"{name}: dangerous tools must ship an example_conversation."
        )


async def test_sliver_nondangerous_tools_carry_core_guidance():
    """Non-dangerous tools still need core guidance for routing decisions."""

    specs = _specs_by_name()
    for name in (
        "sliver_stop_server",
        "sliver_server_status",
        "sliver_list_sessions",
        "sliver_list_listeners",
    ):
        spec = specs[name]
        assert not spec.dangerous, f"{name}: unexpectedly dangerous."
        assert spec.when_to_use, f"{name}: when_to_use is empty."
        assert spec.prerequisites, f"{name}: prerequisites is empty."
        assert spec.follow_ups, f"{name}: follow_ups is empty."
        assert spec.local_model_hints, f"{name}: local_model_hints missing."
        assert spec.pitfalls, f"{name}: pitfalls missing."


async def test_sliver_all_schema_props_have_descriptions():
    specs = _specs_by_name()
    for name in SLIVER_TOOLS:
        spec = specs[name]
        props = spec.input_schema.get("properties") or {}
        for prop_name, prop_def in props.items():
            assert "description" in prop_def and prop_def["description"].strip(), (
                f"{name}.{prop_name}: missing input_schema description (RFC-B05b)."
            )


async def test_sliver_ops_guidance_treats_errors_as_stop_signals():
    specs = _specs_by_name()
    expectations = {
        "sliver_stop_server": ("error", "zero sessions"),
        "sliver_list_sessions": ("errors", "STOP"),
        "sliver_list_listeners": ("errors", "STOP"),
        "sliver_generate_implant": ("error", "STOP"),
        "sliver_execute_in_session": ("errors", "STOP"),
    }

    for name, required_terms in expectations.items():
        text = specs[name].render_full_description()
        for term in required_terms:
            assert term in text, f"{name}: missing low-param stop guidance for {term!r}."
