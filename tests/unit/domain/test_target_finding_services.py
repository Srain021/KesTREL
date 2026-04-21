"""Tests for TargetService + FindingService."""

from __future__ import annotations

import pytest

from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.errors import InvalidStateTransitionError
from kestrel_mcp.domain.services import (
    EngagementService,
    FindingService,
    TargetService,
)

pytestmark = pytest.mark.asyncio


async def _eng(sm):
    return await EngagementService(sm).create(
        name="e",
        display_name="e",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )


# ----- TargetService -----


async def test_target_add_idempotent(sm):
    e = await _eng(sm)
    svc = TargetService(sm)
    t1 = await svc.add(engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/")
    t2 = await svc.add(engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/")
    assert t1.id == t2.id


async def test_target_list_filters_kind(sm):
    e = await _eng(sm)
    svc = TargetService(sm)
    await svc.add(engagement_id=e.id, kind=ent.TargetKind.URL, value="http://a/")
    await svc.add(engagement_id=e.id, kind=ent.TargetKind.IPV4, value="10.0.0.1")
    urls = await svc.list_for_engagement(e.id, kind=ent.TargetKind.URL)
    ips = await svc.list_for_engagement(e.id, kind=ent.TargetKind.IPV4)
    assert len(urls) == 1
    assert len(ips) == 1


async def test_target_enrichment_merges(sm):
    e = await _eng(sm)
    svc = TargetService(sm)
    t = await svc.add(engagement_id=e.id, kind=ent.TargetKind.IPV4, value="10.0.0.1")
    t = await svc.update_enrichment(t.id, open_ports=[80, 443])
    t = await svc.update_enrichment(t.id, open_ports=[443, 22])
    assert t.open_ports == [22, 80, 443]  # sorted + deduped


# ----- FindingService -----


async def test_finding_create_and_count(sm):
    e = await _eng(sm)
    tgt = await TargetService(sm).add(
        engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/"
    )
    fsvc = FindingService(sm)
    await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="SQLi",
        severity=ent.FindingSeverity.CRITICAL,
        discovered_by_tool="nuclei",
    )
    await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="XSS",
        severity=ent.FindingSeverity.MEDIUM,
        discovered_by_tool="dalfox",
    )

    counts = await fsvc.count_by_severity(e.id)
    assert counts[ent.FindingSeverity.CRITICAL] == 1
    assert counts[ent.FindingSeverity.MEDIUM] == 1
    assert counts[ent.FindingSeverity.LOW] == 0


async def test_finding_list_filters(sm):
    e = await _eng(sm)
    tgt = await TargetService(sm).add(
        engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/"
    )
    fsvc = FindingService(sm)
    await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="a",
        severity=ent.FindingSeverity.HIGH,
        discovered_by_tool="t",
    )
    await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="b",
        severity=ent.FindingSeverity.LOW,
        discovered_by_tool="t",
    )

    highs = await fsvc.list_for_engagement(e.id, severity=ent.FindingSeverity.HIGH)
    assert len(highs) == 1
    assert highs[0].title == "a"


async def test_finding_transition_valid_sequence(sm):
    e = await _eng(sm)
    tgt = await TargetService(sm).add(
        engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/"
    )
    fsvc = FindingService(sm)
    f = await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="x",
        severity=ent.FindingSeverity.HIGH,
        discovered_by_tool="t",
    )
    f = await fsvc.transition(f.id, ent.FindingStatus.TRIAGED, note="first look")
    assert f.status == ent.FindingStatus.TRIAGED
    assert "first look" in f.triage_notes

    f = await fsvc.transition(f.id, ent.FindingStatus.CONFIRMED)
    assert f.status == ent.FindingStatus.CONFIRMED

    f = await fsvc.transition(f.id, ent.FindingStatus.FIXED)
    assert f.status == ent.FindingStatus.FIXED
    assert f.fixed_at is not None


async def test_finding_invalid_transition_rejected(sm):
    e = await _eng(sm)
    tgt = await TargetService(sm).add(
        engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/"
    )
    fsvc = FindingService(sm)
    f = await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="x",
        severity=ent.FindingSeverity.HIGH,
        discovered_by_tool="t",
    )
    # NEW can go to TRIAGED, not FIXED
    with pytest.raises(InvalidStateTransitionError):
        await fsvc.transition(f.id, ent.FindingStatus.FIXED)


async def test_finding_terminal_states(sm):
    e = await _eng(sm)
    tgt = await TargetService(sm).add(
        engagement_id=e.id, kind=ent.TargetKind.URL, value="http://x/"
    )
    fsvc = FindingService(sm)
    f = await fsvc.create(
        engagement_id=e.id,
        target_id=tgt.id,
        title="x",
        severity=ent.FindingSeverity.HIGH,
        discovered_by_tool="t",
    )
    await fsvc.transition(f.id, ent.FindingStatus.FALSE_POSITIVE)
    with pytest.raises(InvalidStateTransitionError):
        await fsvc.transition(f.id, ent.FindingStatus.TRIAGED)
