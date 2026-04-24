"""Tests for :class:`ScopeService`."""

from __future__ import annotations

import pytest

from redteam_mcp.domain import entities as ent
from redteam_mcp.domain.errors import ScopeViolationError
from redteam_mcp.domain.services import EngagementService, ScopeService


pytestmark = pytest.mark.asyncio


async def _make_engagement(sm):
    svc = EngagementService(sm)
    return await svc.create(
        name="s", display_name="s",
        engagement_type=ent.EngagementType.CTF, client="c",
    )


async def test_empty_scope_denies_all(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    with pytest.raises(ScopeViolationError):
        await scope.ensure(e.id, "example.com", tool_name="t")


async def test_add_and_list_is_idempotent(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "*.lab.test")
    await scope.add_entry(e.id, "*.lab.test")  # dup
    await scope.add_entry(e.id, "10.0.0.0/16")
    entries = await scope.list_entries(e.id)
    assert len(entries) == 2


async def test_classify_kinds(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "exact.example.com")
    await scope.add_entry(e.id, "*.wild.example.com")
    await scope.add_entry(e.id, ".apex.example.com")
    await scope.add_entry(e.id, "10.0.0.0/8")
    await scope.add_entry(e.id, "10.1.2.3")
    entries = {ee.pattern: ee.kind for ee in await scope.list_entries(e.id)}
    assert entries["exact.example.com"] == ent.ScopeEntryKind.HOSTNAME_EXACT
    assert entries["*.wild.example.com"] == ent.ScopeEntryKind.HOSTNAME_WILDCARD
    assert entries[".apex.example.com"] == ent.ScopeEntryKind.HOSTNAME_APEX_WILDCARD
    assert entries["10.0.0.0/8"] == ent.ScopeEntryKind.CIDR_V4
    assert entries["10.1.2.3"] == ent.ScopeEntryKind.IP_V4


async def test_wildcard_does_not_match_apex(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "*.lab.test")
    await scope.ensure(e.id, "api.lab.test", tool_name="t")
    with pytest.raises(ScopeViolationError):
        await scope.ensure(e.id, "lab.test", tool_name="t")


async def test_apex_wildcard_matches_both(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, ".lab.test")
    await scope.ensure(e.id, "lab.test", tool_name="t")
    await scope.ensure(e.id, "api.lab.test", tool_name="t")


async def test_cidr_ipv4(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "10.10.11.0/24")
    await scope.ensure(e.id, "10.10.11.42", tool_name="t")
    with pytest.raises(ScopeViolationError):
        await scope.ensure(e.id, "10.10.12.42", tool_name="t")


async def test_url_target_extraction(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "*.lab.test")
    await scope.ensure(e.id, "https://api.lab.test/v1/users?id=1", tool_name="t")


async def test_exclusion_wins(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "*.lab.test")
    await scope.add_entry(e.id, "admin.lab.test", included=False)

    await scope.ensure(e.id, "api.lab.test", tool_name="t")
    with pytest.raises(ScopeViolationError):
        await scope.ensure(e.id, "admin.lab.test", tool_name="t")


async def test_remove_entry(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    await scope.add_entry(e.id, "*.lab.test")
    removed = await scope.remove_entry(e.id, "*.lab.test")
    assert removed == 1
    with pytest.raises(ScopeViolationError):
        await scope.ensure(e.id, "api.lab.test", tool_name="t")


async def test_scope_isolated_per_engagement(sm):
    """Adding a pattern in engagement A must not affect engagement B."""

    eng_svc = EngagementService(sm)
    a = await eng_svc.create(name="a", display_name="a", engagement_type=ent.EngagementType.CTF, client="c")
    b = await eng_svc.create(name="b", display_name="b", engagement_type=ent.EngagementType.CTF, client="c")
    scope = ScopeService(sm)
    await scope.add_entry(a.id, "*.a.test")

    await scope.ensure(a.id, "x.a.test", tool_name="t")
    with pytest.raises(ScopeViolationError):
        await scope.ensure(b.id, "x.a.test", tool_name="t")


async def test_bulk_import(sm):
    e = await _make_engagement(sm)
    scope = ScopeService(sm)
    added = await scope.import_patterns(e.id, ["a.com", "*.b.com", "10.0.0.0/16"])
    assert added == 3
    entries = await scope.list_entries(e.id)
    assert len(entries) == 3
