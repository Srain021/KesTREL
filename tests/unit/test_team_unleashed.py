"""Tests for RFC-T00: scope_enforcement three-state switch in server._check_scope."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from redteam_mcp.domain.errors import ScopeViolationError
from redteam_mcp.features import FeatureFlags
from redteam_mcp.security import AuthorizationError, ScopeGuard
from redteam_mcp.server import RedTeamMCPServer


def _fake_server(scope_enforcement: str, authorized_scope: list[str] | None = None):
    """Build a minimal object with the attributes _check_scope reads."""
    fake = MagicMock(spec=RedTeamMCPServer)
    fake.settings = MagicMock()
    fake.settings.features = FeatureFlags(scope_enforcement=scope_enforcement)
    fake.scope_guard = ScopeGuard(authorized_scope or [])
    fake.log = MagicMock()
    return fake


def _fake_ctx_no_engagement():
    ctx = MagicMock()
    ctx.has_engagement.return_value = False
    ctx.engagement_id = None
    return ctx


@pytest.mark.asyncio
async def test_strict_raises_on_empty_scope():
    fake = _fake_server("strict", authorized_scope=[])
    ctx = _fake_ctx_no_engagement()
    with pytest.raises(AuthorizationError):
        await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")


@pytest.mark.asyncio
async def test_strict_raises_on_out_of_scope():
    fake = _fake_server("strict", authorized_scope=["example.com"])
    ctx = _fake_ctx_no_engagement()
    with pytest.raises(AuthorizationError):
        await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")


@pytest.mark.asyncio
async def test_strict_passes_on_in_scope():
    fake = _fake_server("strict", authorized_scope=["example.com"])
    ctx = _fake_ctx_no_engagement()
    # No exception expected.
    await RedTeamMCPServer._check_scope(fake, ctx, "example.com", "tool_x")


@pytest.mark.asyncio
async def test_warn_only_logs_out_of_scope_but_allows():
    fake = _fake_server("warn_only", authorized_scope=["example.com"])
    ctx = _fake_ctx_no_engagement()
    # Should NOT raise.
    await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")
    # Should have emitted a warning.
    fake.log.warning.assert_called_once()
    args, kwargs = fake.log.warning.call_args
    assert args[0] == "scope.warn_only"
    assert kwargs.get("target") == "attacker.io"
    assert kwargs.get("tool") == "tool_x"


@pytest.mark.asyncio
async def test_warn_only_still_logs_on_empty_scope():
    # Empty scope normally raises "authorized_scope is empty".
    fake = _fake_server("warn_only", authorized_scope=[])
    ctx = _fake_ctx_no_engagement()
    await RedTeamMCPServer._check_scope(fake, ctx, "anywhere.io", "tool_x")
    fake.log.warning.assert_called_once()


@pytest.mark.asyncio
async def test_off_skips_check_entirely():
    # Even an empty scope is silently accepted.
    fake = _fake_server("off", authorized_scope=[])
    ctx = _fake_ctx_no_engagement()
    await RedTeamMCPServer._check_scope(fake, ctx, "wherever.io", "tool_x")
    # No log call expected — check was short-circuited.
    fake.log.warning.assert_not_called()


@pytest.mark.asyncio
async def test_warn_only_handles_scope_service_violation():
    # When ctx has an engagement, ensure_scope is used; simulate it raising.
    fake = _fake_server("warn_only", authorized_scope=["example.com"])
    ctx = MagicMock()
    ctx.has_engagement.return_value = True
    ctx.engagement_id = "00000000-0000-0000-0000-000000000001"

    async def _raise(*a, **kw):
        raise ScopeViolationError(
            "out of scope",
            engagement_id=ctx.engagement_id,
            tool="tool_x",
            target="attacker.io",
        )

    ctx.ensure_scope = _raise
    # Should NOT raise.
    await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")
    fake.log.warning.assert_called_once()


@pytest.mark.asyncio
async def test_strict_propagates_scope_service_violation():
    fake = _fake_server("strict", authorized_scope=["example.com"])
    ctx = MagicMock()
    ctx.has_engagement.return_value = True
    ctx.engagement_id = "00000000-0000-0000-0000-000000000001"

    async def _raise(*a, **kw):
        raise ScopeViolationError(
            "out of scope",
            engagement_id=ctx.engagement_id,
            tool="tool_x",
            target="attacker.io",
        )

    ctx.ensure_scope = _raise
    with pytest.raises(ScopeViolationError):
        await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")
