"""FindingService — lifecycle of vulnerability findings."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from ...logging import audit_event
from .. import entities as ent
from ..errors import InvalidStateTransitionError
from ..storage import FindingRow
from ._base import _ServiceBase


_ALLOWED_TRANSITIONS: dict[ent.FindingStatus, set[ent.FindingStatus]] = {
    ent.FindingStatus.NEW: {
        ent.FindingStatus.TRIAGED,
        ent.FindingStatus.FALSE_POSITIVE,
        ent.FindingStatus.CLOSED_WONTFIX,
    },
    ent.FindingStatus.TRIAGED: {
        ent.FindingStatus.CONFIRMED,
        ent.FindingStatus.FALSE_POSITIVE,
        ent.FindingStatus.CLOSED_WONTFIX,
    },
    ent.FindingStatus.CONFIRMED: {
        ent.FindingStatus.FIXED,
        ent.FindingStatus.CLOSED_WONTFIX,
    },
    ent.FindingStatus.FIXED: set(),
    ent.FindingStatus.CLOSED_WONTFIX: set(),
    ent.FindingStatus.FALSE_POSITIVE: set(),
}


class FindingService(_ServiceBase):
    async def create(
        self,
        *,
        engagement_id: UUID,
        target_id: UUID,
        title: str,
        severity: ent.FindingSeverity,
        discovered_by_tool: str,
        **kwargs: object,
    ) -> ent.Finding:
        entity = ent.Finding(
            engagement_id=engagement_id,
            target_id=target_id,
            title=title,
            severity=severity,
            discovered_by_tool=discovered_by_tool,
            **kwargs,  # type: ignore[arg-type]
        )
        async with self._session() as s:
            s.add(_to_row(entity))
            audit_event(
                self.log,
                "finding.create",
                engagement_id=str(engagement_id),
                target_id=str(target_id),
                severity=severity.value,
                tool=discovered_by_tool,
            )
        return entity

    async def bulk_create(
        self,
        findings: list[ent.Finding],
    ) -> int:
        if not findings:
            return 0
        async with self._session() as s:
            for f in findings:
                s.add(_to_row(f))
            audit_event(self.log, "finding.bulk_create", count=len(findings))
        return len(findings)

    async def get(self, finding_id: UUID) -> ent.Finding | None:
        async with self._session() as s:
            row = await s.get(FindingRow, finding_id)
        return _to_entity(row) if row else None

    async def list_for_engagement(
        self,
        engagement_id: UUID,
        *,
        status: ent.FindingStatus | None = None,
        severity: ent.FindingSeverity | None = None,
        target_id: UUID | None = None,
    ) -> list[ent.Finding]:
        async with self._session() as s:
            stmt = (
                select(FindingRow)
                .where(FindingRow.engagement_id == engagement_id)
                .order_by(FindingRow.discovered_at.desc())
            )
            if status is not None:
                stmt = stmt.where(FindingRow.status == status)
            if severity is not None:
                stmt = stmt.where(FindingRow.severity == severity)
            if target_id is not None:
                stmt = stmt.where(FindingRow.target_id == target_id)
            rows = (await s.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def count_by_severity(
        self,
        engagement_id: UUID,
    ) -> dict[ent.FindingSeverity, int]:
        result: dict[ent.FindingSeverity, int] = {sev: 0 for sev in ent.FindingSeverity}
        findings = await self.list_for_engagement(engagement_id)
        for f in findings:
            result[f.severity] += 1
        return result

    async def transition(
        self,
        finding_id: UUID,
        new_status: ent.FindingStatus,
        *,
        note: str = "",
    ) -> ent.Finding:
        async with self._session() as s:
            row = await s.get(FindingRow, finding_id)
            if row is None:
                raise ValueError(f"finding {finding_id} not found")
            current = row.status
            if new_status not in _ALLOWED_TRANSITIONS.get(current, set()):
                raise InvalidStateTransitionError(
                    f"Cannot move finding from '{current.value}' to '{new_status.value}'.",
                    finding_id=str(finding_id),
                    from_status=current.value,
                    to_status=new_status.value,
                )
            row.status = new_status
            if note:
                row.triage_notes = (row.triage_notes + "\n" + note).strip()
            if new_status == ent.FindingStatus.FIXED:
                row.fixed_at = datetime.now(timezone.utc)
            audit_event(
                self.log,
                "finding.transition",
                finding_id=str(finding_id),
                from_status=current.value,
                to_status=new_status.value,
            )
        return await self.get(finding_id)  # type: ignore[return-value]


def _to_row(e: ent.Finding) -> FindingRow:
    return FindingRow(
        id=e.id,
        engagement_id=e.engagement_id,
        target_id=e.target_id,
        title=e.title,
        severity=e.severity,
        confidence=e.confidence,
        category=e.category,
        cwe_json=list(e.cwe),
        cve_json=list(e.cve),
        owasp_top10_json=list(e.owasp_top10),
        mitre_attack_json=list(e.mitre_attack),
        cvss_vector=e.cvss_vector,
        cvss_score=e.cvss_score,
        description=e.description,
        impact=e.impact,
        remediation=e.remediation,
        references_json=list(e.references),
        evidence_json=[ev.model_dump(mode="json") for ev in e.evidence],
        discovered_by_tool=e.discovered_by_tool,
        discovered_at=e.discovered_at,
        verified=e.verified,
        verified_by=e.verified_by,
        verified_at=e.verified_at,
        status=e.status,
        triage_notes=e.triage_notes,
        fixed_at=e.fixed_at,
        group_id=e.group_id,
    )


def _to_entity(r: FindingRow) -> ent.Finding:
    return ent.Finding(
        id=r.id,
        engagement_id=r.engagement_id,
        target_id=r.target_id,
        title=r.title,
        severity=r.severity,
        confidence=r.confidence,
        category=r.category,
        cwe=list(r.cwe_json or []),
        cve=list(r.cve_json or []),
        owasp_top10=list(r.owasp_top10_json or []),
        mitre_attack=list(r.mitre_attack_json or []),
        cvss_vector=r.cvss_vector,
        cvss_score=r.cvss_score,
        description=r.description,
        impact=r.impact,
        remediation=r.remediation,
        references=list(r.references_json or []),
        evidence=[ent.FindingEvidence.model_validate(ev) for ev in (r.evidence_json or [])],
        discovered_by_tool=r.discovered_by_tool,
        discovered_at=r.discovered_at,
        verified=r.verified,
        verified_by=r.verified_by,
        verified_at=r.verified_at,
        status=r.status,
        triage_notes=r.triage_notes,
        fixed_at=r.fixed_at,
        group_id=r.group_id,
    )
