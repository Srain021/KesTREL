"""Tests for the Sliver tool module.

Starts as a regression guard for RFC-B05b1 (guidance completeness on server
lifecycle + run_command). B05b2 will expand to cover the remaining 4 ops
tools; handler-level tests live outside this RFC's scope.
"""

from __future__ import annotations

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.sliver_tool import SliverModule


def _specs_by_name() -> dict[str, object]:
    module = SliverModule(Settings(), ScopeGuard([]))
    return {spec.name: spec for spec in module.specs()}


# Tools covered by RFC-B05b1. B05b2 will extend this set.
B05B1_TOOLS = (
    "sliver_start_server",
    "sliver_stop_server",
    "sliver_server_status",
    "sliver_run_command",
)


async def test_sliver_b1_tools_exist():
    specs = _specs_by_name()
    for name in B05B1_TOOLS:
        assert name in specs, f"{name} missing from SliverModule.specs()"


async def test_sliver_b1_dangerous_tools_carry_full_guidance():
    """Dangerous tools get ALL guidance fields populated (RFC-B05b1).

    Non-dangerous server-status/stop have looser requirements (see the next test).
    """

    specs = _specs_by_name()
    dangerous_names = {"sliver_start_server", "sliver_run_command"}
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
                f"{name}: guidance field '{field_name}' is empty (RFC-B05b1)."
            )
        assert spec.local_model_hints, f"{name}: local_model_hints missing."
        assert spec.example_conversation, (
            f"{name}: dangerous tools must ship an example_conversation."
        )


async def test_sliver_b1_nondangerous_tools_carry_core_guidance():
    """Non-dangerous tools still need when_to_use + local_model_hints + pitfalls."""

    specs = _specs_by_name()
    for name in ("sliver_stop_server", "sliver_server_status"):
        spec = specs[name]
        assert not spec.dangerous, f"{name}: unexpectedly dangerous."
        assert spec.when_to_use, f"{name}: when_to_use is empty."
        assert spec.local_model_hints, f"{name}: local_model_hints missing."
        assert spec.pitfalls, f"{name}: pitfalls missing."


async def test_sliver_b1_all_schema_props_have_descriptions():
    specs = _specs_by_name()
    for name in B05B1_TOOLS:
        spec = specs[name]
        props = spec.input_schema.get("properties") or {}
        for prop_name, prop_def in props.items():
            assert "description" in prop_def and prop_def["description"].strip(), (
                f"{name}.{prop_name}: missing input_schema description (RFC-B05b1)."
            )
