"""ToolInvocationService — audit-layer persistence for every tool call."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...logging import audit_event
from .. import entities as ent
from ..storage import ToolInvocationRow
from ._base import _ServiceBase

_NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")
_ZERO_HASH = "0" * 64


class ToolInvocationService(_ServiceBase):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessionmaker)
        self._chain_heads: dict[UUID, str] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def record(
        self,
        *,
        engagement_id: UUID,
        actor_id: UUID | None,
        tool_name: str,
        arguments: dict[str, Any],
        started_at: datetime,
        completed_at: datetime,
        exit_code: int | None = None,
        truncated: bool = False,
        timed_out: bool = False,
        findings_created: list[UUID] | None = None,
        credentials_created: list[UUID] | None = None,
        artifacts_created: list[UUID] | None = None,
        targets_created: list[UUID] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ent.ToolInvocation:
        """Persist a single tool invocation to the audit table.

        This is a **fire-and-forget** operation from the caller's perspective:
        it should be awaited but wrapped in ``try/except`` so a DB write
        failure never bubbles up to the LLM user.
        """

        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        actor_id = actor_id or _NIL_UUID

        sanitized = _sanitize_arguments(arguments)
        arguments_hash = _sha256_hex(json.dumps(sanitized, sort_keys=True, default=str))

        lock = await self._lock_for(engagement_id)
        async with lock:
            async with self._session() as s:
                prev_hash = self._chain_heads.get(engagement_id)
                if prev_hash is None:
                    prev_hash = await _fetch_prev_hash(s, engagement_id)

                findings_created = findings_created or []
                credentials_created = credentials_created or []
                artifacts_created = artifacts_created or []
                targets_created = targets_created or []
                this_hash = _compute_this_hash(
                    prev_hash=prev_hash,
                    engagement_id=engagement_id,
                    actor_id=actor_id,
                    tool_name=tool_name,
                    arguments_sanitized=sanitized,
                    arguments_hash=arguments_hash,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                    truncated=truncated,
                    timed_out=timed_out,
                    findings_created=findings_created,
                    credentials_created=credentials_created,
                    artifacts_created=artifacts_created,
                    targets_created=targets_created,
                    error_code=error_code,
                    error_message=error_message,
                )
                entity = ent.ToolInvocation(
                    id=uuid4(),
                    engagement_id=engagement_id,
                    actor_id=actor_id,
                    tool_name=tool_name,
                    arguments_sanitized=sanitized,
                    arguments_hash=arguments_hash,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                    truncated=truncated,
                    timed_out=timed_out,
                    findings_created=findings_created,
                    credentials_created=credentials_created,
                    artifacts_created=artifacts_created,
                    targets_created=targets_created,
                    error_code=error_code,
                    error_message=error_message,
                    prev_hash=prev_hash,
                    this_hash=this_hash,
                )

                row = _to_row(entity)
                s.add(row)

            self._chain_heads[engagement_id] = entity.this_hash

        audit_event(
            self.log,
            "tool_invocation.record",
            tool_name=tool_name,
            engagement_id=str(engagement_id),
            duration_ms=duration_ms,
            exit_code=exit_code,
        )
        return entity

    async def _lock_for(self, engagement_id: UUID) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(engagement_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[engagement_id] = lock
            return lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "key",
    "credential",
    "credentials",
    "private_key",
    "cert",
    "certificate",
}


def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return a recursively sanitized copy with sensitive values redacted."""

    return {key: _sanitize_named_value(key, value) for key, value in arguments.items()}


def _sanitize_named_value(key: object, value: Any) -> Any:
    if _is_sensitive_key(str(key)):
        return "***REDACTED***"
    return _sanitize_value(value)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sanitize_named_value(key, item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitize_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower().replace("-", "_")
    if lower in _SENSITIVE_KEYS:
        return True
    return any(lower.endswith(suffix) for suffix in ("_password", "_token", "_secret", "_key"))


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


async def _fetch_prev_hash(session: AsyncSession, engagement_id: UUID) -> str:
    """Return the current chain head for an engagement from persisted rows."""

    result = await session.execute(
        select(ToolInvocationRow.this_hash)
        .where(ToolInvocationRow.engagement_id == engagement_id)
        .order_by(
            ToolInvocationRow.completed_at.desc(),
            ToolInvocationRow.started_at.desc(),
        )
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row is not None else _ZERO_HASH


def _compute_this_hash(
    *,
    prev_hash: str,
    engagement_id: UUID,
    actor_id: UUID,
    tool_name: str,
    arguments_sanitized: dict[str, Any],
    arguments_hash: str,
    started_at: datetime,
    completed_at: datetime,
    duration_ms: int,
    exit_code: int | None,
    truncated: bool,
    timed_out: bool,
    findings_created: list[UUID],
    credentials_created: list[UUID],
    artifacts_created: list[UUID],
    targets_created: list[UUID],
    error_code: str | None,
    error_message: str | None,
) -> str:
    """Hash chain: SHA256(prev_hash || canonical_json(record payload))."""

    payload = {
        "engagement_id": str(engagement_id),
        "actor_id": str(actor_id),
        "tool_name": tool_name,
        "arguments_sanitized": arguments_sanitized,
        "arguments_hash": arguments_hash,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "truncated": truncated,
        "timed_out": timed_out,
        "findings_created": [str(f) for f in findings_created],
        "credentials_created": [str(c) for c in credentials_created],
        "artifacts_created": [str(a) for a in artifacts_created],
        "targets_created": [str(t) for t in targets_created],
        "error_code": error_code,
        "error_message": error_message,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256_hex(prev_hash + canonical)


def _to_row(entity: ent.ToolInvocation) -> ToolInvocationRow:
    return ToolInvocationRow(
        id=entity.id,
        engagement_id=entity.engagement_id,
        actor_id=entity.actor_id,
        tool_name=entity.tool_name,
        arguments_sanitized_json=entity.arguments_sanitized,
        arguments_hash=entity.arguments_hash,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
        duration_ms=entity.duration_ms,
        exit_code=entity.exit_code,
        truncated=entity.truncated,
        timed_out=entity.timed_out,
        findings_created_json=[str(f) for f in entity.findings_created],
        credentials_created_json=[str(c) for c in entity.credentials_created],
        artifacts_created_json=[str(a) for a in entity.artifacts_created],
        targets_created_json=[str(t) for t in entity.targets_created],
        error_code=entity.error_code,
        error_message=entity.error_message,
        prev_hash=entity.prev_hash,
        this_hash=entity.this_hash,
    )
