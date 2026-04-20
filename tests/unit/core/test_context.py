"""Tests for RequestContext + ContextVar plumbing.

Scenarios covered
-----------------
* bind / unbind lifecycle
* nested ``with`` correctly restores outer context
* parallel asyncio tasks each see their own context (critical guarantee)
* require_engagement raises when none
* ensure_scope no-ops without engagement but enforces with one
"""

from __future__ import annotations

import asyncio

import pytest

from redteam_mcp.core import (
    RequestContext,
    ServiceContainer,
    bind_context,
    current_context,
    current_context_or_none,
)
from redteam_mcp.core.context import (
    NoActiveContextError,
    NoActiveEngagementError,
)
from redteam_mcp.domain import entities as ent
from redteam_mcp.domain.errors import ScopeViolationError

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


async def test_no_context_raises(container):
    assert current_context_or_none() is None
    with pytest.raises(NoActiveContextError):
        current_context()


async def test_open_context_binds_and_unbinds(container):
    async with container.open_context() as ctx:
        cur = current_context()
        assert cur is ctx
        assert not ctx.has_engagement()
    assert current_context_or_none() is None


async def test_nested_contexts_restore_outer(container):
    outer_id = None
    inner_id = None

    async with container.open_context() as outer:
        outer_id = id(outer)
        assert current_context() is outer
        async with container.open_context() as inner:
            inner_id = id(inner)
            assert current_context() is inner
        # back to outer after inner exits
        assert current_context() is outer
    assert outer_id != inner_id


async def test_require_engagement_without_raises(container):
    async with container.open_context() as ctx:
        with pytest.raises(NoActiveEngagementError):
            ctx.require_engagement()


async def test_require_engagement_with(container):
    e = await container.engagement.create(
        name="x",
        display_name="x",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    async with container.open_context(engagement_id=e.id) as ctx:
        assert ctx.require_engagement() == e.id
        assert ctx.has_engagement()


async def test_ensure_scope_noop_without_engagement(container):
    async with container.open_context() as ctx:
        # No engagement - ensure_scope must silently pass.
        await ctx.ensure_scope("anything.example.com", tool_name="t")


async def test_ensure_scope_rejects_out_of_scope(container):
    e = await container.engagement.create(
        name="x",
        display_name="x",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    await container.scope.add_entry(e.id, "*.lab.test")
    async with container.open_context(engagement_id=e.id) as ctx:
        await ctx.ensure_scope("api.lab.test", tool_name="t")  # passes
        with pytest.raises(ScopeViolationError):
            await ctx.ensure_scope("evil.com", tool_name="t")


async def test_parallel_tasks_see_own_contexts(container):
    """Two asyncio tasks must each keep their own context."""

    a = await container.engagement.create(
        name="a",
        display_name="a",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    b = await container.engagement.create(
        name="b",
        display_name="b",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )

    leaked: dict[str, object] = {}

    async def worker(name: str, eid):
        async with container.open_context(engagement_id=eid):
            # Yield to the other task to maximise interleaving
            await asyncio.sleep(0)
            leaked[name] = current_context().engagement_id

    await asyncio.gather(
        worker("a", a.id),
        worker("b", b.id),
    )

    assert leaked == {"a": a.id, "b": b.id}


async def test_bind_context_manual(container):
    """Lower-level :func:`bind_context` also works independently."""

    ctx = RequestContext(container=container, engagement_id=None)
    with bind_context(ctx):
        assert current_context() is ctx
    assert current_context_or_none() is None


async def test_dry_run_flag_propagates(container):
    async with container.open_context(dry_run=True):
        assert current_context().dry_run is True
