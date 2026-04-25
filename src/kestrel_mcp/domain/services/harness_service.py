"""Persistence service for HARNESS sessions and planned steps."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from .. import entities as ent
from ..storage import HarnessSessionRow, HarnessStepRow
from ._base import _ServiceBase


def _now() -> datetime:
    return datetime.now(timezone.utc)


class HarnessService(_ServiceBase):
    async def create_session(
        self,
        *,
        goal: str,
        target: str | None,
        engagement_id: UUID | None,
        mode: str,
        model_tier: str,
    ) -> ent.HarnessSession:
        now = _now()
        entity = ent.HarnessSession(
            id=uuid4(),
            engagement_id=engagement_id,
            goal=goal,
            target=target,
            mode=mode,
            model_tier=model_tier,
            state_summary=f"Goal: {goal}" + (f"; target: {target}" if target else ""),
            created_at=now,
            updated_at=now,
        )
        async with self._session() as s:
            s.add(_session_to_row(entity))
        return entity

    async def get_session(self, session_id: UUID) -> ent.HarnessSession | None:
        async with self._session() as s:
            row = await s.get(HarnessSessionRow, session_id)
            return _session_from_row(row) if row else None

    async def update_session(
        self,
        session_id: UUID,
        *,
        status: ent.HarnessSessionStatus | None = None,
        state_summary: str | None = None,
    ) -> ent.HarnessSession | None:
        async with self._session() as s:
            row = await s.get(HarnessSessionRow, session_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if state_summary is not None:
                row.state_summary = state_summary
            row.updated_at = _now()
            await s.flush()
            return _session_from_row(row)

    async def add_step(
        self,
        *,
        session_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        status: ent.HarnessStepStatus,
        risk_level: str,
        recommended_model_tier: str,
        reason: str,
    ) -> ent.HarnessStep:
        now = _now()
        ordinal = await self._next_ordinal(session_id)
        entity = ent.HarnessStep(
            id=uuid4(),
            session_id=session_id,
            ordinal=ordinal,
            tool_name=tool_name,
            arguments=arguments,
            status=status,
            risk_level=risk_level,
            recommended_model_tier=recommended_model_tier,
            reason=reason,
            result_summary=None,
            tool_invocation_id=None,
            created_at=now,
            updated_at=now,
        )
        async with self._session() as s:
            s.add(_step_to_row(entity))
        return entity

    async def get_step(self, step_id: UUID) -> ent.HarnessStep | None:
        async with self._session() as s:
            row = await s.get(HarnessStepRow, step_id)
            return _step_from_row(row) if row else None

    async def list_steps(self, session_id: UUID) -> list[ent.HarnessStep]:
        async with self._session() as s:
            rows = (
                await s.execute(
                    select(HarnessStepRow)
                    .where(HarnessStepRow.session_id == session_id)
                    .order_by(HarnessStepRow.ordinal)
                )
            ).scalars()
            return [_step_from_row(row) for row in rows]

    async def update_step(
        self,
        step_id: UUID,
        *,
        status: ent.HarnessStepStatus | None = None,
        result_summary: str | None = None,
        tool_invocation_id: UUID | None = None,
    ) -> ent.HarnessStep | None:
        async with self._session() as s:
            row = await s.get(HarnessStepRow, step_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if result_summary is not None:
                row.result_summary = result_summary
            if tool_invocation_id is not None:
                row.tool_invocation_id = tool_invocation_id
            row.updated_at = _now()
            await s.flush()
            return _step_from_row(row)

    async def get_state_payload(self, session_id: UUID) -> dict[str, Any] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        steps = await self.list_steps(session_id)
        return {
            "session": session.model_dump(mode="json"),
            "steps": [step.model_dump(mode="json") for step in steps],
        }

    async def _next_ordinal(self, session_id: UUID) -> int:
        steps = await self.list_steps(session_id)
        return len(steps) + 1


def _session_to_row(entity: ent.HarnessSession) -> HarnessSessionRow:
    return HarnessSessionRow(
        id=entity.id,
        engagement_id=entity.engagement_id,
        goal=entity.goal,
        target=entity.target,
        status=entity.status,
        mode=entity.mode,
        model_tier=entity.model_tier,
        state_summary=entity.state_summary,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _session_from_row(row: HarnessSessionRow) -> ent.HarnessSession:
    return ent.HarnessSession(
        id=row.id,
        engagement_id=row.engagement_id,
        goal=row.goal,
        target=row.target,
        status=row.status,
        mode=row.mode,
        model_tier=row.model_tier,
        state_summary=row.state_summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _step_to_row(entity: ent.HarnessStep) -> HarnessStepRow:
    return HarnessStepRow(
        id=entity.id,
        session_id=entity.session_id,
        ordinal=entity.ordinal,
        tool_name=entity.tool_name,
        arguments_json=entity.arguments,
        status=entity.status,
        risk_level=entity.risk_level,
        recommended_model_tier=entity.recommended_model_tier,
        reason=entity.reason,
        result_summary=entity.result_summary,
        tool_invocation_id=entity.tool_invocation_id,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _step_from_row(row: HarnessStepRow) -> ent.HarnessStep:
    return ent.HarnessStep(
        id=row.id,
        session_id=row.session_id,
        ordinal=row.ordinal,
        tool_name=row.tool_name,
        arguments=row.arguments_json,
        status=row.status,
        risk_level=row.risk_level,
        recommended_model_tier=row.recommended_model_tier,
        reason=row.reason,
        result_summary=row.result_summary,
        tool_invocation_id=row.tool_invocation_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
