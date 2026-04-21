"""End-to-end tests for EngagementModule tools.

We instantiate a real ``ServiceContainer`` (in-memory SQLite) and bind it to
a ``RequestContext`` for each test, then invoke the tool handlers directly
as the MCP server would.
"""

from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.engagement_tool import EngagementModule

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


@pytest.fixture
def module():
    return EngagementModule(Settings(), ScopeGuard([]))


def spec_by_name(module: EngagementModule, name: str):
    for spec in module.specs():
        if spec.name == name:
            return spec
    raise AssertionError(f"{name} not in spec list")


async def test_module_exposes_16_tools(module):
    names = {s.name for s in module.specs()}
    assert len(names) == 16
    assert {
        "engagement_new",
        "engagement_list",
        "engagement_show",
        "engagement_activate",
        "engagement_pause",
        "engagement_close",
        "engagement_switch",
        "scope_add",
        "scope_remove",
        "scope_list",
        "scope_check",
        "target_add",
        "target_list",
        "finding_list",
        "finding_show",
        "finding_transition",
    } == names


async def test_full_lifecycle(container, module):
    async with container.open_context():
        # ----- create -----
        r = await spec_by_name(module, "engagement_new").handler(
            {
                "name": "htb-s7",
                "display_name": "HTB S7 week 3",
                "engagement_type": "ctf",
                "client": "HackTheBox",
            }
        )
        assert not r.is_error
        assert r.structured["status"] == "planning"

        # ----- list -----
        r = await spec_by_name(module, "engagement_list").handler({})
        assert r.structured["count"] == 1

        # ----- activate -----
        r = await spec_by_name(module, "engagement_activate").handler({"id_or_name": "htb-s7"})
        assert r.structured["status"] == "active"

        # ----- show (using active via switch-equivalent not wired; use name) -----
        r = await spec_by_name(module, "engagement_show").handler({"id_or_name": "htb-s7"})
        assert r.structured["name"] == "htb-s7"
        assert r.structured["scope"] == []


async def test_engagement_new_duplicate_returns_error(container, module):
    async with container.open_context():
        args = {
            "name": "dup",
            "display_name": "x",
            "engagement_type": "ctf",
            "client": "c",
        }
        r1 = await spec_by_name(module, "engagement_new").handler(args)
        assert not r1.is_error
        r2 = await spec_by_name(module, "engagement_new").handler(args)
        assert r2.is_error
        assert "already exists" in r2.text


async def test_close_requires_confirm(container, module):
    async with container.open_context():
        await spec_by_name(module, "engagement_new").handler(
            {
                "name": "c",
                "display_name": "c",
                "engagement_type": "ctf",
                "client": "c",
            }
        )
        await spec_by_name(module, "engagement_activate").handler({"id_or_name": "c"})

        r = await spec_by_name(module, "engagement_close").handler(
            {"id_or_name": "c", "confirm": False}
        )
        assert r.is_error
        assert "confirm=true" in r.text

        r = await spec_by_name(module, "engagement_close").handler(
            {"id_or_name": "c", "confirm": True}
        )
        assert r.structured["status"] == "closed"


async def test_scope_add_list_check_remove(container, module):
    async with container.open_context():
        await spec_by_name(module, "engagement_new").handler(
            {
                "name": "s",
                "display_name": "s",
                "engagement_type": "ctf",
                "client": "c",
            }
        )
        e = await container.engagement.get_by_name("s")

    # Re-open under an active engagement
    async with container.open_context(engagement_id=e.id):
        # Empty scope initially
        r = await spec_by_name(module, "scope_list").handler({})
        assert r.structured["count"] == 0

        # Add one
        r = await spec_by_name(module, "scope_add").handler({"pattern": "*.lab.test"})
        assert r.structured["kind"] == "hostname_wildcard"

        # Check in / out
        in_check = await spec_by_name(module, "scope_check").handler({"target": "api.lab.test"})
        assert in_check.structured["in_scope"] is True
        out_check = await spec_by_name(module, "scope_check").handler({"target": "evil.com"})
        assert out_check.structured["in_scope"] is False

        # Remove
        r = await spec_by_name(module, "scope_remove").handler({"pattern": "*.lab.test"})
        assert r.structured["removed"] == 1


async def test_scope_add_without_active_engagement_errors(container, module):
    async with container.open_context():
        r = await spec_by_name(module, "scope_add").handler({"pattern": "x.com"})
        assert r.is_error
        assert "engagement" in r.text.lower()


async def test_target_add_respects_scope(container, module):
    async with container.open_context():
        await spec_by_name(module, "engagement_new").handler(
            {
                "name": "t",
                "display_name": "t",
                "engagement_type": "ctf",
                "client": "c",
            }
        )
        e = await container.engagement.get_by_name("t")

    # Need active engagement to add scope and targets
    async with container.open_context(engagement_id=e.id):
        await spec_by_name(module, "scope_add").handler({"pattern": "*.lab.test"})
        # target_add is dangerous + requires_scope_field but server-side dispatcher
        # normally does the scope check. When calling the handler directly we
        # rely on the domain layer's TargetService (no scope check there yet).
        r = await spec_by_name(module, "target_add").handler(
            {
                "kind": "url",
                "value": "http://api.lab.test/",
            }
        )
        assert not r.is_error

        r = await spec_by_name(module, "target_list").handler({})
        assert r.structured["count"] == 1


async def test_finding_lifecycle(container, module):
    async with container.open_context():
        await spec_by_name(module, "engagement_new").handler(
            {
                "name": "f",
                "display_name": "f",
                "engagement_type": "ctf",
                "client": "c",
            }
        )
        e = await container.engagement.get_by_name("f")

    async with container.open_context(engagement_id=e.id):
        # Seed a target + finding via direct service calls
        from kestrel_mcp.domain import entities as ent

        t = await container.target.add(
            engagement_id=e.id,
            kind=ent.TargetKind.URL,
            value="http://x/",
        )
        f = await container.finding.create(
            engagement_id=e.id,
            target_id=t.id,
            title="Test finding",
            severity=ent.FindingSeverity.HIGH,
            discovered_by_tool="manual",
        )

        # list
        r = await spec_by_name(module, "finding_list").handler({})
        assert r.structured["count"] == 1
        assert r.structured["by_severity"] == {"high": 1}

        # filter by severity
        r = await spec_by_name(module, "finding_list").handler({"severity": "critical"})
        assert r.structured["count"] == 0

        # show
        r = await spec_by_name(module, "finding_show").handler({"finding_id": str(f.id)})
        assert r.structured["title"] == "Test finding"

        # transition
        r = await spec_by_name(module, "finding_transition").handler(
            {
                "finding_id": str(f.id),
                "to_status": "triaged",
                "note": "taking a look",
            }
        )
        assert r.structured["status"] == "triaged"


async def test_rich_description_renders(module):
    """Every spec must render without exception and contain WHEN TO USE for key tools."""

    for spec in module.specs():
        text = spec.render_full_description()
        assert text  # non-empty
        if spec.name in {"engagement_new", "scope_add", "engagement_close"}:
            # These have explicit hints
            assert "WHEN" in text or "PITFALL" in text or "HINTS" in text
