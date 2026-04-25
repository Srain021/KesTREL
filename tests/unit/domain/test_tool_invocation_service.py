"""Tests for ToolInvocationService chain and sanitization behavior."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.services import EngagementService, ToolInvocationService
from kestrel_mcp.domain.services.tool_invocation_service import _ZERO_HASH
from kestrel_mcp.domain.storage import ToolInvocationRow

pytestmark = pytest.mark.asyncio


def _ts(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)


async def _engagement_id(sm) -> object:
    engagement = await EngagementService(sm).create(
        name="audit",
        display_name="Audit",
        engagement_type=ent.EngagementType.CTF,
        client="client",
    )
    return engagement.id


async def _rows(sm) -> list[ToolInvocationRow]:
    async with sm() as session:
        result = await session.execute(
            select(ToolInvocationRow).order_by(ToolInvocationRow.completed_at)
        )
        return list(result.scalars())


async def test_record_redacts_nested_sensitive_arguments(sm) -> None:
    engagement_id = await _engagement_id(sm)
    svc = ToolInvocationService(sm)

    invocation = await svc.record(
        engagement_id=engagement_id,
        actor_id=None,
        tool_name="demo",
        arguments={
            "password": "rootpw",
            "nested": {
                "token": "abc123",
                "items": [
                    {"api_key": "secret"},
                    {"safe": "value"},
                ],
            },
            "client_secret": "nested-secret",
        },
        started_at=_ts(0),
        completed_at=_ts(1),
    )

    assert invocation.arguments_sanitized["password"] == "***REDACTED***"
    assert invocation.arguments_sanitized["nested"]["token"] == "***REDACTED***"
    assert invocation.arguments_sanitized["nested"]["items"][0]["api_key"] == "***REDACTED***"
    assert invocation.arguments_sanitized["nested"]["items"][1]["safe"] == "value"
    assert invocation.arguments_sanitized["client_secret"] == "***REDACTED***"

    rows = await _rows(sm)
    assert rows[0].arguments_sanitized_json["nested"]["token"] == "***REDACTED***"


async def test_record_chain_follows_last_persisted_row_not_latest_started_at(sm) -> None:
    engagement_id = await _engagement_id(sm)
    svc = ToolInvocationService(sm)

    first = await svc.record(
        engagement_id=engagement_id,
        actor_id=None,
        tool_name="first",
        arguments={"step": 1},
        started_at=_ts(10),
        completed_at=_ts(11),
    )
    second = await svc.record(
        engagement_id=engagement_id,
        actor_id=None,
        tool_name="second",
        arguments={"step": 2},
        started_at=_ts(0),
        completed_at=_ts(12),
    )
    third = await svc.record(
        engagement_id=engagement_id,
        actor_id=None,
        tool_name="third",
        arguments={"step": 3},
        started_at=_ts(12),
        completed_at=_ts(13),
    )

    assert first.prev_hash == _ZERO_HASH
    assert second.prev_hash == first.this_hash
    assert third.prev_hash == second.this_hash


async def test_concurrent_records_form_single_hash_chain(sm) -> None:
    engagement_id = await _engagement_id(sm)
    svc = ToolInvocationService(sm)

    async def one(index: int):
        return await svc.record(
            engagement_id=engagement_id,
            actor_id=None,
            tool_name=f"tool-{index}",
            arguments={"index": index},
            started_at=_ts(index),
            completed_at=_ts(index + 1),
        )

    invocations = await asyncio.gather(*(one(index) for index in range(8)))

    zero_heads = [inv for inv in invocations if inv.prev_hash == _ZERO_HASH]
    prev_hashes = {inv.prev_hash for inv in invocations if inv.prev_hash != _ZERO_HASH}
    this_hashes = {inv.this_hash for inv in invocations}

    assert len(zero_heads) == 1
    assert len(prev_hashes) == len(invocations) - 1
    assert prev_hashes <= this_hashes

    rows = await _rows(sm)
    assert len(rows) == 8
