"""Rate limiter unit tests."""

from __future__ import annotations

import asyncio

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.core import RequestContext, ServiceContainer
from kestrel_mcp.core.rate_limit import RateLimitedError, RateLimiter, RateLimitSpec
from kestrel_mcp.server import RedTeamMCPServer
from kestrel_mcp.tools.base import ToolResult, ToolSpec

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


async def _noop_handler(arguments: dict[str, object]) -> ToolResult:
    return ToolResult(text=f"ok:{sorted(arguments)}")


async def test_initial_burst_allowed():
    limiter = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=3)

    for _ in range(3):
        await limiter.acquire("tool", spec)


async def test_over_limit_refused():
    limiter = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=2)

    await limiter.acquire("tool", spec)
    await limiter.acquire("tool", spec)

    with pytest.raises(RateLimitedError) as exc_info:
        await limiter.acquire("tool", spec)

    assert exc_info.value.retry_after_sec > 0
    assert exc_info.value.http_like_status == 429


async def test_refill_after_sleep():
    limiter = RateLimiter()
    spec = RateLimitSpec(per_minute=600, burst=1)

    await limiter.acquire("key", spec)
    with pytest.raises(RateLimitedError):
        await limiter.acquire("key", spec)

    await asyncio.sleep(0.15)
    await limiter.acquire("key", spec)


async def test_different_keys_independent():
    limiter = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=1)

    await limiter.acquire("a", spec)
    await limiter.acquire("b", spec)

    with pytest.raises(RateLimitedError):
        await limiter.acquire("a", spec)


async def test_gc_removes_idle():
    limiter = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=1)

    await limiter.acquire("idle-key", spec)
    assert "idle-key" in limiter._buckets

    limiter._buckets["idle-key"].last_access -= 3600
    removed = await limiter.gc()

    assert removed >= 1
    assert "idle-key" not in limiter._buckets


async def test_concurrent_calls_do_not_overshoot():
    limiter = RateLimiter()
    spec = RateLimitSpec(per_minute=0.01, burst=5)

    successes = 0
    failures = 0

    async def one() -> None:
        nonlocal successes, failures
        try:
            await limiter.acquire("parallel", spec)
            successes += 1
        except RateLimitedError:
            failures += 1

    await asyncio.gather(*(one() for _ in range(20)))

    assert successes == 5
    assert failures == 15


async def test_server_skips_rate_limit_when_feature_disabled(container):
    server = RedTeamMCPServer(Settings.build(edition="team"), container=container)
    ctx = RequestContext(container=container, engagement_id=None)
    spec = ToolSpec(
        name="demo",
        description="demo",
        input_schema={},
        handler=_noop_handler,
        rate_limit=RateLimitSpec(per_minute=60, burst=1),
    )

    await server._apply_rate_limit(ctx, "demo", spec)
    await server._apply_rate_limit(ctx, "demo", spec)

    assert server.limiter._buckets == {}


async def test_server_applies_rate_limit_when_feature_enabled(container):
    server = RedTeamMCPServer(Settings.build(edition="pro"), container=container)
    ctx = RequestContext(container=container, engagement_id=None)
    spec = ToolSpec(
        name="demo",
        description="demo",
        input_schema={},
        handler=_noop_handler,
        rate_limit=RateLimitSpec(per_minute=60, burst=1),
    )

    await server._apply_rate_limit(ctx, "demo", spec)
    with pytest.raises(RateLimitedError):
        await server._apply_rate_limit(ctx, "demo", spec)
