"""EngagementService — CRUD + lifecycle state machine for Engagements."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...logging import audit_event
from .. import entities as ent
from ..errors import (
    EngagementNotFoundError,
    EngagementStateError,
    InvalidStateTransitionError,
    UniqueConstraintError,
)
from ..storage import EngagementRow
from ._base import _ServiceBase

# State machine (see DOMAIN_MODEL.md §3.2)
_TRANSITIONS: dict[ent.EngagementStatus, set[ent.EngagementStatus]] = {
    ent.EngagementStatus.PLANNING: {ent.EngagementStatus.ACTIVE, ent.EngagementStatus.CLOSED},
    ent.EngagementStatus.ACTIVE: {ent.EngagementStatus.PAUSED, ent.EngagementStatus.CLOSED},
    ent.EngagementStatus.PAUSED: {ent.EngagementStatus.ACTIVE, ent.EngagementStatus.CLOSED},
    ent.EngagementStatus.CLOSED: set(),  # terminal
}


class EngagementService(_ServiceBase):
    """Manage the lifecycle of Engagement entities."""

    async def create(
        self,
        *,
        name: str,
        display_name: str,
        engagement_type: ent.EngagementType,
        client: str,
        owners: Iterable[UUID] | None = None,
        authorization_doc_ref: str | None = None,
        expires_at: datetime | None = None,
    ) -> ent.Engagement:
        """Create a new engagement in PLANNING state."""

        entity = ent.Engagement(
            name=name,
            display_name=display_name,
            engagement_type=engagement_type,
            client=client,
            owners=list(owners or []),
            authorization_doc_ref=authorization_doc_ref,
            expires_at=expires_at,
        )

        try:
            async with self._session() as s:
                s.add(_entity_to_row(entity))
        except IntegrityError as exc:
            raise UniqueConstraintError(
                f"Engagement name '{name}' already exists.",
                name=name,
            ) from exc

        audit_event(self.log, "engagement.create", engagement_id=str(entity.id), name=name)
        return entity

    async def get(self, engagement_id: UUID) -> ent.Engagement:
        async with self._session() as s:
            row = await s.get(EngagementRow, engagement_id)
        if row is None:
            raise EngagementNotFoundError(
                f"Engagement {engagement_id} not found.",
                engagement_id=str(engagement_id),
            )
        return _row_to_entity(row)

    async def get_by_name(self, name: str) -> ent.Engagement:
        async with self._session() as s:
            stmt = select(EngagementRow).where(EngagementRow.name == name.lower())
            row = (await s.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise EngagementNotFoundError(
                f"Engagement with name '{name}' not found.",
                name=name,
            )
        return _row_to_entity(row)

    async def list(
        self,
        *,
        status: ent.EngagementStatus | None = None,
    ) -> list[ent.Engagement]:
        async with self._session() as s:
            stmt = select(EngagementRow).order_by(EngagementRow.created_at.desc())
            if status is not None:
                stmt = stmt.where(EngagementRow.status == status)
            rows = (await s.execute(stmt)).scalars().all()
        return [_row_to_entity(r) for r in rows]

    async def transition(
        self,
        engagement_id: UUID,
        new_status: ent.EngagementStatus,
    ) -> ent.Engagement:
        """Move an engagement to ``new_status`` per the state machine."""

        async with self._session() as s:
            row = await s.get(EngagementRow, engagement_id)
            if row is None:
                raise EngagementNotFoundError(
                    f"Engagement {engagement_id} not found.",
                    engagement_id=str(engagement_id),
                )
            current = row.status
            if new_status not in _TRANSITIONS.get(current, set()):
                raise InvalidStateTransitionError(
                    f"Cannot move engagement from '{current.value}' to "
                    f"'{new_status.value}'. Allowed from current: "
                    f"{sorted(s.value for s in _TRANSITIONS.get(current, set()))}.",
                    engagement_id=str(engagement_id),
                    from_status=current.value,
                    to_status=new_status.value,
                )

            row.status = new_status
            now = _now()
            row.updated_at = now
            if new_status == ent.EngagementStatus.ACTIVE and row.started_at is None:
                row.started_at = now
            if new_status == ent.EngagementStatus.CLOSED:
                row.closed_at = now
            audit_event(
                self.log,
                "engagement.transition",
                engagement_id=str(engagement_id),
                from_status=current.value,
                to_status=new_status.value,
            )

        return await self.get(engagement_id)

    async def ensure_mutable(self, engagement_id: UUID) -> ent.Engagement:
        """Fetch the engagement and verify it accepts mutations."""

        e = await self.get(engagement_id)
        if not e.is_mutable():
            raise EngagementStateError(
                f"Engagement '{e.name}' is in state {e.status.value}; mutations not allowed.",
                engagement_id=str(engagement_id),
                status=e.status.value,
            )
        return e

    async def ensure_accepts_dangerous(self, engagement_id: UUID) -> ent.Engagement:
        """Fetch engagement; raise if dangerous tools are not allowed."""

        e = await self.get(engagement_id)
        if not e.allows_dangerous_tools():
            reason = "engagement expired" if e.is_expired() else f"status is {e.status.value}"
            raise EngagementStateError(
                f"Engagement '{e.name}' does not allow dangerous tools ({reason}).",
                engagement_id=str(engagement_id),
                status=e.status.value,
                expired=e.is_expired(),
            )
        return e


# ---------------------------------------------------------------------------
# Mappers
# ---------------------------------------------------------------------------


def _entity_to_row(e: ent.Engagement) -> EngagementRow:
    return EngagementRow(
        id=e.id,
        name=e.name,
        display_name=e.display_name,
        status=e.status,
        engagement_type=e.engagement_type,
        client=e.client,
        owners_json=[str(o) for o in e.owners],
        authorization_doc_ref=e.authorization_doc_ref,
        started_at=e.started_at,
        expires_at=e.expires_at,
        closed_at=e.closed_at,
        dry_run=e.dry_run,
        opsec_mode=e.opsec_mode,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def _row_to_entity(r: EngagementRow) -> ent.Engagement:
    return ent.Engagement(
        id=r.id,
        name=r.name,
        display_name=r.display_name,
        status=r.status,
        engagement_type=r.engagement_type,
        client=r.client,
        owners=[UUID(x) if isinstance(x, str) else x for x in (r.owners_json or [])],
        authorization_doc_ref=r.authorization_doc_ref,
        started_at=r.started_at,
        expires_at=r.expires_at,
        closed_at=r.closed_at,
        dry_run=r.dry_run,
        opsec_mode=r.opsec_mode,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)
