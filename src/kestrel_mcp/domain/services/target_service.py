"""TargetService — CRUD for Target entities, bound to an engagement."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from ...logging import audit_event
from .. import entities as ent
from ..storage import TargetRow
from ._base import _ServiceBase


class TargetService(_ServiceBase):
    async def add(
        self,
        *,
        engagement_id: UUID,
        kind: ent.TargetKind,
        value: str,
        parent_id: UUID | None = None,
        discovered_by_tool: str | None = None,
    ) -> ent.Target:
        """Create or return existing target (dedup by (engagement_id, kind, value))."""

        async with self._session() as s:
            existing = await s.execute(
                select(TargetRow).where(
                    TargetRow.engagement_id == engagement_id,
                    TargetRow.kind == kind,
                    TargetRow.value == value,
                )
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                return _to_entity(row)

            entity = ent.Target(
                engagement_id=engagement_id,
                kind=kind,
                value=value,
                parent_id=parent_id,
                discovered_by_tool=discovered_by_tool,
            )
            s.add(_to_row(entity))
            audit_event(
                self.log,
                "target.add",
                engagement_id=str(engagement_id),
                kind=kind.value,
                value=value,
            )
            return entity

    async def get(self, target_id: UUID) -> ent.Target | None:
        async with self._session() as s:
            row = await s.get(TargetRow, target_id)
        return _to_entity(row) if row else None

    async def list_for_engagement(
        self,
        engagement_id: UUID,
        *,
        kind: ent.TargetKind | None = None,
    ) -> list[ent.Target]:
        async with self._session() as s:
            stmt = select(TargetRow).where(TargetRow.engagement_id == engagement_id)
            if kind is not None:
                stmt = stmt.where(TargetRow.kind == kind)
            rows = (await s.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def update_enrichment(
        self,
        target_id: UUID,
        *,
        open_ports: list[int] | None = None,
        tech_stack: list[str] | None = None,
        hostnames: list[str] | None = None,
        organization: str | None = None,
        country: str | None = None,
        tags: list[str] | None = None,
    ) -> ent.Target:
        """Merge-patch observable attributes collected by probes."""

        async with self._session() as s:
            row = await s.get(TargetRow, target_id)
            if row is None:
                raise ValueError(f"target {target_id} not found")
            if open_ports is not None:
                row.open_ports_json = sorted(set(list(row.open_ports_json) + open_ports))
            if tech_stack is not None:
                row.tech_stack_json = sorted(set(list(row.tech_stack_json) + tech_stack))
            if hostnames is not None:
                row.hostnames_json = sorted(set(list(row.hostnames_json) + hostnames))
            if organization is not None:
                row.organization = organization
            if country is not None:
                row.country = country
            if tags is not None:
                row.tags_json = sorted(set(list(row.tags_json) + tags))
            row.last_scanned_at = datetime.now(timezone.utc)
            return _to_entity(row)


def _to_row(e: ent.Target) -> TargetRow:
    return TargetRow(
        id=e.id,
        engagement_id=e.engagement_id,
        kind=e.kind,
        value=e.value,
        parent_id=e.parent_id,
        discovered_by_tool=e.discovered_by_tool,
        discovered_at=e.discovered_at,
        open_ports_json=list(e.open_ports),
        tech_stack_json=list(e.tech_stack),
        hostnames_json=list(e.hostnames),
        organization=e.organization,
        country=e.country,
        last_scanned_at=e.last_scanned_at,
        notes=e.notes,
        tags_json=list(e.tags),
    )


def _to_entity(r: TargetRow) -> ent.Target:
    return ent.Target(
        id=r.id,
        engagement_id=r.engagement_id,
        kind=r.kind,
        value=r.value,
        parent_id=r.parent_id,
        discovered_by_tool=r.discovered_by_tool,
        discovered_at=r.discovered_at,
        open_ports=list(r.open_ports_json or []),
        tech_stack=list(r.tech_stack_json or []),
        hostnames=list(r.hostnames_json or []),
        organization=r.organization,
        country=r.country,
        last_scanned_at=r.last_scanned_at,
        notes=r.notes,
        tags=list(r.tags_json or []),
    )
