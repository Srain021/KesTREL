"""ScopeService — persistent, engagement-scoped authorization.

This replaces the in-memory :class:`redteam_mcp.security.ScopeGuard`, keeping
the same matching semantics but backing it with the engagement DB so rules
survive restart and can be shared across MCP / REST / TUI.

Matching semantics (same as the original ScopeGuard):

* exact hostname          ``host.example.com``
* wildcard hostname       ``*.example.com``   matches one-plus labels
* bare-dot hostname       ``.example.com``    matches apex and any subdomain
* IPv4 / IPv6             ``10.0.0.1``
* CIDR v4 / v6            ``10.0.0.0/16``
* URL path                ``https://example.com/api/*``  (hostname extracted)

Exclusion rule: if any matching entry has ``included=False``, the target is
denied regardless of inclusions. This is a safety override.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import select

from ...logging import audit_event
from .. import entities as ent
from ..errors import ScopeViolationError
from ..storage import ScopeEntryRow, ScopeRow
from ._base import _ServiceBase


_IP_V4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


# ---------------------------------------------------------------------------
# In-memory matching primitives (shared with the old security module logic)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CompiledEntry:
    """Parsed scope entry ready for O(1) matching."""

    raw: str
    kind: ent.ScopeEntryKind
    included: bool


def _classify(pattern: str) -> ent.ScopeEntryKind:
    """Best-effort classification for a scope string."""

    p = pattern.strip()
    if "://" in p or (p.startswith("/") and "." not in p.split("/")[0]):
        return ent.ScopeEntryKind.URL_PATH
    if "/" in p:
        try:
            net = ipaddress.ip_network(p, strict=False)
        except ValueError:
            return ent.ScopeEntryKind.HOSTNAME_WILDCARD
        return (
            ent.ScopeEntryKind.CIDR_V6
            if isinstance(net, ipaddress.IPv6Network)
            else ent.ScopeEntryKind.CIDR_V4
        )
    if p.startswith("*."):
        return ent.ScopeEntryKind.HOSTNAME_WILDCARD
    if p.startswith("."):
        return ent.ScopeEntryKind.HOSTNAME_APEX_WILDCARD
    try:
        addr = ipaddress.ip_address(p)
    except ValueError:
        return ent.ScopeEntryKind.HOSTNAME_EXACT
    return (
        ent.ScopeEntryKind.IP_V6
        if isinstance(addr, ipaddress.IPv6Address)
        else ent.ScopeEntryKind.IP_V4
    )


def _extract_host(target: str) -> str | None:
    target = target.strip()
    if not target:
        return None
    if "://" in target:
        parsed = urlparse(target)
        return parsed.hostname or None
    if "/" in target:
        # Could be a URL-ish without scheme or a CIDR — prefer splitting on "/"
        try:
            ipaddress.ip_network(target, strict=False)
            return None  # CIDR, no single host to extract
        except ValueError:
            pass
        return target.split("/", 1)[0] or None
    if ":" in target and target.count(":") == 1:
        try:
            ipaddress.ip_address(target)
            return target  # IPv6 sort of — let caller handle
        except ValueError:
            pass
        return target.split(":", 1)[0] or None
    return target


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _match(entry: _CompiledEntry, target: str) -> bool:
    raw = entry.raw.strip().lower()
    kind = entry.kind

    # URL and bare hostname handling share an extracted host
    host = _extract_host(target)
    if host is None:
        # Target is a CIDR or similar — only IP-family entries could match
        try:
            tgt_net = ipaddress.ip_network(target, strict=False)
        except ValueError:
            return False
        if kind in (ent.ScopeEntryKind.CIDR_V4, ent.ScopeEntryKind.CIDR_V6):
            try:
                return ipaddress.ip_network(raw, strict=False).supernet_of(tgt_net)
            except ValueError:
                return False
        return False

    host = host.lower()

    if kind in (ent.ScopeEntryKind.CIDR_V4, ent.ScopeEntryKind.CIDR_V6):
        if not _is_ip(host):
            return False
        try:
            return ipaddress.ip_address(host) in ipaddress.ip_network(raw, strict=False)
        except ValueError:
            return False

    if kind in (ent.ScopeEntryKind.IP_V4, ent.ScopeEntryKind.IP_V6):
        if not _is_ip(host):
            return False
        try:
            return ipaddress.ip_address(host) == ipaddress.ip_address(raw)
        except ValueError:
            return False

    if kind == ent.ScopeEntryKind.HOSTNAME_EXACT:
        return host == raw

    if kind == ent.ScopeEntryKind.HOSTNAME_WILDCARD:
        suffix = raw[2:]  # skip "*."
        return host.endswith("." + suffix)

    if kind == ent.ScopeEntryKind.HOSTNAME_APEX_WILDCARD:
        base = raw[1:]  # skip "."
        return host == base or host.endswith("." + base)

    if kind == ent.ScopeEntryKind.URL_PATH:
        # Only exact-hostname-match for now; path prefix left as TODO
        raw_host = urlparse(raw).hostname
        return bool(raw_host) and host == raw_host

    return False


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


class ScopeService(_ServiceBase):
    """CRUD + authorization for engagement scope.

    The primary authorization entry point is :meth:`ensure`, which mirrors
    the old ``ScopeGuard.ensure`` semantics but reads current state from
    the DB every call. Services that need to check thousands of targets
    per second should batch via :meth:`snapshot`.
    """

    # ------ read-side ------

    async def snapshot(self, engagement_id: UUID) -> tuple[_CompiledEntry, ...]:
        """Return an immutable tuple of compiled entries for bulk matching."""

        async with self._session() as s:
            stmt = (
                select(ScopeEntryRow)
                .join(ScopeRow, ScopeRow.id == ScopeEntryRow.scope_id)
                .where(ScopeRow.engagement_id == engagement_id)
            )
            rows = (await s.execute(stmt)).scalars().all()

        compiled = tuple(
            _CompiledEntry(raw=r.pattern, kind=r.kind, included=r.included) for r in rows
        )
        return compiled

    async def ensure(self, engagement_id: UUID, target: str, *, tool_name: str) -> None:
        """Raise :class:`ScopeViolationError` if ``target`` is out of scope."""

        snap = await self.snapshot(engagement_id)
        self._enforce(snap, target, tool_name=tool_name, engagement_id=engagement_id)

    def ensure_against(
        self,
        snapshot: tuple[_CompiledEntry, ...],
        target: str,
        *,
        tool_name: str,
        engagement_id: UUID,
    ) -> None:
        """Bulk variant: reuse an already-fetched snapshot."""

        self._enforce(snapshot, target, tool_name=tool_name, engagement_id=engagement_id)

    def _enforce(
        self,
        entries: tuple[_CompiledEntry, ...],
        target: str,
        *,
        tool_name: str,
        engagement_id: UUID,
    ) -> None:
        if not entries:
            raise ScopeViolationError(
                f"Tool '{tool_name}' refused: engagement has an empty scope. "
                "Use scope_add to declare authorized targets before running offensive tools.",
                engagement_id=str(engagement_id),
                tool=tool_name,
                target=target,
            )
        matched_include = False
        for e in entries:
            if _match(e, target):
                if not e.included:
                    raise ScopeViolationError(
                        f"Tool '{tool_name}' refused: target '{target}' matches an "
                        f"EXCLUSION rule ('{e.raw}').",
                        engagement_id=str(engagement_id),
                        tool=tool_name,
                        target=target,
                        blocked_by=e.raw,
                    )
                matched_include = True
        if not matched_include:
            raise ScopeViolationError(
                f"Tool '{tool_name}' refused: target '{target}' is not within the "
                "authorized engagement scope.",
                engagement_id=str(engagement_id),
                tool=tool_name,
                target=target,
            )

    # ------ write-side ------

    async def add_entry(
        self,
        engagement_id: UUID,
        pattern: str,
        *,
        included: bool = True,
        note: str | None = None,
        added_by: UUID | None = None,
    ) -> ent.ScopeEntry:
        """Add (or return existing) scope entry. Idempotent on (pattern, included)."""

        kind = _classify(pattern)
        async with self._session() as s:
            scope = await self._get_or_create_scope(s, engagement_id)

            # Dedup — explicit query (no lazy-load of relationship)
            existing = (
                await s.execute(
                    select(ScopeEntryRow).where(
                        ScopeEntryRow.scope_id == scope.id,
                        ScopeEntryRow.pattern == pattern,
                        ScopeEntryRow.included == included,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return _to_entity_entry(existing)

            row = ScopeEntryRow(
                id=uuid4(),
                scope_id=scope.id,
                pattern=pattern,
                kind=kind,
                included=included,
                note=note,
                added_by=added_by,
                added_at=_now(),
            )
            s.add(row)
            await s.flush()
            audit_event(
                self.log,
                "scope.add",
                engagement_id=str(engagement_id),
                pattern=pattern,
                included=included,
            )
            return _to_entity_entry(row)

    async def remove_entry(self, engagement_id: UUID, pattern: str) -> int:
        """Remove every entry matching ``pattern``. Returns count removed."""

        async with self._session() as s:
            stmt = (
                select(ScopeEntryRow)
                .join(ScopeRow, ScopeRow.id == ScopeEntryRow.scope_id)
                .where(
                    ScopeRow.engagement_id == engagement_id,
                    ScopeEntryRow.pattern == pattern,
                )
            )
            rows = (await s.execute(stmt)).scalars().all()
            for r in rows:
                await s.delete(r)
            audit_event(
                self.log,
                "scope.remove",
                engagement_id=str(engagement_id),
                pattern=pattern,
                removed=len(rows),
            )
            return len(rows)

    async def list_entries(self, engagement_id: UUID) -> list[ent.ScopeEntry]:
        async with self._session() as s:
            stmt = (
                select(ScopeEntryRow)
                .join(ScopeRow, ScopeRow.id == ScopeEntryRow.scope_id)
                .where(ScopeRow.engagement_id == engagement_id)
                .order_by(ScopeEntryRow.added_at)
            )
            rows = (await s.execute(stmt)).scalars().all()
        return [_to_entity_entry(r) for r in rows]

    async def import_patterns(
        self,
        engagement_id: UUID,
        patterns: list[str],
        *,
        added_by: UUID | None = None,
    ) -> int:
        """Bulk add a list of patterns. Returns count newly added."""

        added = 0
        for p in patterns:
            p = p.strip()
            if not p:
                continue
            before = await self._count_entries(engagement_id, p)
            await self.add_entry(engagement_id, p, added_by=added_by)
            after = await self._count_entries(engagement_id, p)
            if after > before:
                added += 1
        return added

    # ------ helpers ------

    async def _get_or_create_scope(self, s, engagement_id: UUID) -> ScopeRow:
        stmt = select(ScopeRow).where(ScopeRow.engagement_id == engagement_id)
        row = (await s.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = ScopeRow(
                id=uuid4(),
                engagement_id=engagement_id,
                created_at=_now(),
                updated_at=_now(),
            )
            s.add(row)
            await s.flush()
        return row

    async def _count_entries(self, engagement_id: UUID, pattern: str) -> int:
        async with self._session() as s:
            stmt = (
                select(ScopeEntryRow)
                .join(ScopeRow, ScopeRow.id == ScopeEntryRow.scope_id)
                .where(
                    ScopeRow.engagement_id == engagement_id,
                    ScopeEntryRow.pattern == pattern,
                )
            )
            return len((await s.execute(stmt)).scalars().all())


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _to_entity_entry(row: ScopeEntryRow) -> ent.ScopeEntry:
    return ent.ScopeEntry(
        id=row.id,
        pattern=row.pattern,
        kind=row.kind,
        included=row.included,
        note=row.note,
        added_by=row.added_by,
        added_at=row.added_at,
    )
