"""Integration tests that exercise every module's specs without network."""

from __future__ import annotations

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard


def _all_enabled_settings() -> Settings:
    settings = Settings()
    for tool in type(settings.tools).model_fields:
        block = getattr(settings.tools, tool)
        block.enabled = True
    return settings


class TestToolRegistry:
    def test_all_modules_load_when_enabled(self) -> None:
        settings = _all_enabled_settings()
        guard = ScopeGuard(["*.example.com"])
        from kestrel_mcp.tools import load_modules

        modules = load_modules(settings, guard)
        ids = sorted(m.id for m in modules)
        assert ids == sorted(
            [
                "engagement",  # Sprint 3: domain management module
                "shodan",
                "nuclei",
                "caido",
                "ligolo",
                "sliver",
                "havoc",
                "evilginx",
            ]
        )

    def test_every_spec_has_unique_name(self) -> None:
        settings = _all_enabled_settings()
        guard = ScopeGuard(["*.example.com"])
        from kestrel_mcp.tools import load_modules

        modules = load_modules(settings, guard)
        names: set[str] = set()
        total = 0
        for m in modules:
            for spec in m.specs():
                assert spec.name not in names, f"duplicate name {spec.name}"
                assert spec.name.islower() or "_" in spec.name
                assert spec.input_schema["type"] == "object"
                names.add(spec.name)
                total += 1
        assert total >= 30

    def test_dangerous_tools_are_marked(self) -> None:
        """Every tool that accepts a 'target', 'targets', 'url' or 'callback_addr'
        input must be flagged dangerous OR have ``requires_scope_field`` set,
        UNLESS it is explicitly tagged ``helper`` (purely informational, no
        network / no execution).

        This test only checks the MARKING; actual enforcement is proven by
        the individual module tests that run the handlers.
        """

        settings = _all_enabled_settings()
        guard = ScopeGuard(["*.example.com"])
        from kestrel_mcp.tools import load_modules

        dangerous_indicators = {
            "url",
            "urls",
            "target",
            "targets",
            "callback_addr",
            "phish_hostname",
            "cidr",
        }
        modules = load_modules(settings, guard)
        for m in modules:
            for spec in m.specs():
                props = (spec.input_schema.get("properties") or {}).keys()
                if not (dangerous_indicators & set(props)):
                    continue
                if {"helper", "audit"} & set(spec.tags):
                    # Pure string-generating helpers (e.g. agent one-liner
                    # emitters) don't touch the target themselves — the
                    # operator copy-pastes the output elsewhere.
                    # "audit" tag marks read-only inspection tools
                    # (scope_check, etc.) which also don't touch targets.
                    continue
                assert spec.dangerous or spec.requires_scope_field, (
                    f"{spec.name} accepts a sensitive field but is not marked dangerous "
                    "and has no requires_scope_field"
                )

    def test_workflows_load_when_shodan_enabled(self) -> None:
        settings = _all_enabled_settings()
        guard = ScopeGuard(["*.example.com"])
        from kestrel_mcp.workflows import load_workflow_specs

        specs = load_workflow_specs(settings, guard)
        names = {s.name for s in specs}
        assert "generate_pentest_report" in names
        assert "recon_target" in names
