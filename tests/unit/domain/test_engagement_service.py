"""Tests for :class:`EngagementService`."""

from __future__ import annotations

import pytest

from redteam_mcp.domain import entities as ent
from redteam_mcp.domain.errors import (
    EngagementNotFoundError,
    InvalidStateTransitionError,
    UniqueConstraintError,
)
from redteam_mcp.domain.services import EngagementService

pytestmark = pytest.mark.asyncio


async def test_create_and_get(sm):
    svc = EngagementService(sm)
    e = await svc.create(
        name="demo",
        display_name="Demo",
        engagement_type=ent.EngagementType.CTF,
        client="Demo Co",
    )
    fetched = await svc.get(e.id)
    assert fetched.name == "demo"
    assert fetched.status == ent.EngagementStatus.PLANNING


async def test_unique_name(sm):
    svc = EngagementService(sm)
    await svc.create(
        name="dup",
        display_name="x",
        engagement_type=ent.EngagementType.CTF,
        client="y",
    )
    with pytest.raises(UniqueConstraintError):
        await svc.create(
            name="dup",
            display_name="x2",
            engagement_type=ent.EngagementType.CTF,
            client="y",
        )


async def test_get_by_name_missing(sm):
    svc = EngagementService(sm)
    with pytest.raises(EngagementNotFoundError):
        await svc.get_by_name("nonexistent")


async def test_list_filters_status(sm):
    svc = EngagementService(sm)
    a = await svc.create(
        name="a", display_name="A", engagement_type=ent.EngagementType.CTF, client="c"
    )
    b = await svc.create(
        name="b", display_name="B", engagement_type=ent.EngagementType.CTF, client="c"
    )
    await svc.transition(a.id, ent.EngagementStatus.ACTIVE)

    active = await svc.list(status=ent.EngagementStatus.ACTIVE)
    planning = await svc.list(status=ent.EngagementStatus.PLANNING)
    all_ = await svc.list()

    assert {x.id for x in active} == {a.id}
    assert {x.id for x in planning} == {b.id}
    assert len(all_) == 2


async def test_valid_transition_sequence(sm):
    svc = EngagementService(sm)
    e = await svc.create(
        name="x", display_name="x", engagement_type=ent.EngagementType.CTF, client="c"
    )
    assert e.status == ent.EngagementStatus.PLANNING

    e = await svc.transition(e.id, ent.EngagementStatus.ACTIVE)
    assert e.status == ent.EngagementStatus.ACTIVE
    assert e.started_at is not None

    e = await svc.transition(e.id, ent.EngagementStatus.PAUSED)
    assert e.status == ent.EngagementStatus.PAUSED

    e = await svc.transition(e.id, ent.EngagementStatus.ACTIVE)
    assert e.status == ent.EngagementStatus.ACTIVE

    e = await svc.transition(e.id, ent.EngagementStatus.CLOSED)
    assert e.status == ent.EngagementStatus.CLOSED
    assert e.closed_at is not None


async def test_invalid_transition_rejected(sm):
    svc = EngagementService(sm)
    e = await svc.create(
        name="x", display_name="x", engagement_type=ent.EngagementType.CTF, client="c"
    )
    await svc.transition(e.id, ent.EngagementStatus.ACTIVE)
    with pytest.raises(InvalidStateTransitionError):
        await svc.transition(e.id, ent.EngagementStatus.PLANNING)


async def test_closed_is_terminal(sm):
    svc = EngagementService(sm)
    e = await svc.create(
        name="x", display_name="x", engagement_type=ent.EngagementType.CTF, client="c"
    )
    await svc.transition(e.id, ent.EngagementStatus.ACTIVE)
    await svc.transition(e.id, ent.EngagementStatus.CLOSED)
    with pytest.raises(InvalidStateTransitionError):
        await svc.transition(e.id, ent.EngagementStatus.ACTIVE)


async def test_ensure_mutable_rejects_closed(sm):
    svc = EngagementService(sm)
    e = await svc.create(
        name="x", display_name="x", engagement_type=ent.EngagementType.CTF, client="c"
    )
    await svc.transition(e.id, ent.EngagementStatus.ACTIVE)
    await svc.transition(e.id, ent.EngagementStatus.CLOSED)
    from redteam_mcp.domain.errors import EngagementStateError

    with pytest.raises(EngagementStateError):
        await svc.ensure_mutable(e.id)


async def test_ensure_accepts_dangerous_requires_active(sm):
    svc = EngagementService(sm)
    e = await svc.create(
        name="x", display_name="x", engagement_type=ent.EngagementType.CTF, client="c"
    )
    from redteam_mcp.domain.errors import EngagementStateError

    # Planning — not active
    with pytest.raises(EngagementStateError):
        await svc.ensure_accepts_dangerous(e.id)
    # Activate — should pass
    await svc.transition(e.id, ent.EngagementStatus.ACTIVE)
    await svc.ensure_accepts_dangerous(e.id)
