"""Persistence layer — SQLAlchemy 2.0 async ORM backing the domain entities.

Design principles
-----------------

1. **Separation**: ORM models live here; Pydantic entities live in
   :mod:`.entities`. Services translate between them.  This avoids tight
   coupling to a specific DB and keeps the public API pure Python data.

2. **One engagement = one database file** by default. The default layout is::

       ~/.kestrel/engagements/<slug>/engagement.db     (SQLite)
       ~/.kestrel/engagements/<slug>/artifacts/
       ~/.kestrel/engagements/<slug>/logs/

   This gives natural isolation between engagements. For team use, a single
   shared PostgreSQL URL can replace the per-engagement file — see
   :func:`make_engine`.

3. **Async-first**. All session code is ``AsyncSession``. Sync helpers are
   available for migrations / CLI doctor only.

4. **No business rules here**. Validation, state transitions, and scope
   enforcement belong to services.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from . import entities as ent

# ---------------------------------------------------------------------------
# Custom types
# ---------------------------------------------------------------------------


class UUIDString(TypeDecorator[UUID]):
    """Portable UUID column.

    PostgreSQL has native UUID; SQLite doesn't.  We store as 36-char string
    everywhere for portability.
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: UUID | str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: str | None, dialect: object) -> UUID | None:
        if value is None:
            return None
        return UUID(value)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# ORM models (one table per entity; naming: `<Entity>Row`)
# ---------------------------------------------------------------------------


class EngagementRow(Base):
    __tablename__ = "engagements"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[ent.EngagementStatus] = mapped_column(
        SAEnum(ent.EngagementStatus, name="engagement_status"),
        nullable=False,
        default=ent.EngagementStatus.PLANNING,
    )
    engagement_type: Mapped[ent.EngagementType] = mapped_column(
        SAEnum(ent.EngagementType, name="engagement_type"), nullable=False
    )

    client: Mapped[str] = mapped_column(String(128), nullable=False)
    owners_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    authorization_doc_ref: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opsec_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    scope: Mapped[ScopeRow | None] = relationship(back_populates="engagement", uselist=False)
    targets: Mapped[list[TargetRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    findings: Mapped[list[FindingRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    credentials: Mapped[list[CredentialRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[ArtifactRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[SessionRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    invocations: Mapped[list[ToolInvocationRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    harness_sessions: Mapped[list[HarnessSessionRow]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )


class ScopeRow(Base):
    __tablename__ = "scopes"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    engagement: Mapped[EngagementRow] = relationship(back_populates="scope")
    entries: Mapped[list[ScopeEntryRow]] = relationship(
        back_populates="scope", cascade="all, delete-orphan", order_by="ScopeEntryRow.added_at"
    )


class ScopeEntryRow(Base):
    __tablename__ = "scope_entries"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    scope_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("scopes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pattern: Mapped[str] = mapped_column(String(256), nullable=False)
    kind: Mapped[ent.ScopeEntryKind] = mapped_column(
        SAEnum(ent.ScopeEntryKind, name="scope_entry_kind"), nullable=False
    )
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text)
    added_by: Mapped[UUID | None] = mapped_column(UUIDString())
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scope: Mapped[ScopeRow] = relationship(back_populates="entries")


class TargetRow(Base):
    __tablename__ = "targets"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ent.TargetKind] = mapped_column(
        SAEnum(ent.TargetKind, name="target_kind"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        UUIDString(), ForeignKey("targets.id", ondelete="SET NULL")
    )

    discovered_by_tool: Mapped[str | None] = mapped_column(String(128))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    open_ports_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    tech_stack_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    hostnames_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    organization: Mapped[str | None] = mapped_column(String(256))
    country: Mapped[str | None] = mapped_column(String(8))

    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    engagement: Mapped[EngagementRow] = relationship(back_populates="targets")


class CredentialRow(Base):
    __tablename__ = "credentials"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ent.CredentialKind] = mapped_column(
        SAEnum(ent.CredentialKind, name="credential_kind"), nullable=False
    )
    target_id: Mapped[UUID | None] = mapped_column(
        UUIDString(), ForeignKey("targets.id", ondelete="SET NULL")
    )
    obtained_from_tool: Mapped[str] = mapped_column(String(128), nullable=False)
    obtained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    identity: Mapped[str] = mapped_column(String(256), nullable=False)
    secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    secret_kdf: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_metadata_json: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)

    validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    engagement: Mapped[EngagementRow] = relationship(back_populates="credentials")


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    severity: Mapped[ent.FindingSeverity] = mapped_column(
        SAEnum(ent.FindingSeverity, name="finding_severity"), nullable=False, index=True
    )
    confidence: Mapped[ent.Confidence] = mapped_column(
        SAEnum(ent.Confidence, name="confidence"), nullable=False
    )
    category: Mapped[ent.FindingCategory] = mapped_column(
        SAEnum(ent.FindingCategory, name="finding_category"), nullable=False
    )

    cwe_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cve_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    owasp_top10_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mitre_attack_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cvss_vector: Mapped[str | None] = mapped_column(String(128))
    cvss_score: Mapped[float | None] = mapped_column(Float)

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    impact: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remediation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    references_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    evidence_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    discovered_by_tool: Mapped[str] = mapped_column(String(128), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by: Mapped[UUID | None] = mapped_column(UUIDString())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[ent.FindingStatus] = mapped_column(
        SAEnum(ent.FindingStatus, name="finding_status"),
        nullable=False,
        default=ent.FindingStatus.NEW,
        index=True,
    )
    triage_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group_id: Mapped[UUID | None] = mapped_column(UUIDString())

    engagement: Mapped[EngagementRow] = relationship(back_populates="findings")


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ent.ArtifactKind] = mapped_column(
        SAEnum(ent.ArtifactKind, name="artifact_kind"), nullable=False
    )

    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    produced_by_tool: Mapped[str] = mapped_column(String(128), nullable=False)
    produced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_target_id: Mapped[UUID | None] = mapped_column(UUIDString())

    mime_type: Mapped[str] = mapped_column(
        String(128), nullable=False, default="application/octet-stream"
    )
    original_filename: Mapped[str | None] = mapped_column(String(512))
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    engagement: Mapped[EngagementRow] = relationship(back_populates="artifacts")


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[UUID | None] = mapped_column(
        UUIDString(), ForeignKey("targets.id", ondelete="SET NULL")
    )

    kind: Mapped[ent.SessionKind] = mapped_column(
        SAEnum(ent.SessionKind, name="session_kind"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, default="https")
    callback_addr: Mapped[str] = mapped_column(String(256), nullable=False)

    status: Mapped[ent.SessionStatus] = mapped_column(
        SAEnum(ent.SessionStatus, name="session_status"),
        nullable=False,
        default=ent.SessionStatus.ACTIVE,
        index=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    remote_hostname: Mapped[str | None] = mapped_column(String(256))
    remote_user: Mapped[str | None] = mapped_column(String(256))
    remote_os: Mapped[str | None] = mapped_column(String(128))
    remote_pid: Mapped[int | None] = mapped_column(Integer)
    remote_integrity: Mapped[str | None] = mapped_column(String(32))

    credentials_used_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    findings_produced_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    artifacts_produced_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    engagement: Mapped[EngagementRow] = relationship(back_populates="sessions")


class ToolInvocationRow(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[UUID] = mapped_column(UUIDString(), nullable=False, index=True)

    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    arguments_sanitized_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timed_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    findings_created_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    credentials_created_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    artifacts_created_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    targets_created_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)

    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    this_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    engagement: Mapped[EngagementRow] = relationship(back_populates="invocations")


class HarnessSessionRow(Base):
    __tablename__ = "harness_sessions"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    engagement_id: Mapped[UUID | None] = mapped_column(
        UUIDString(), ForeignKey("engagements.id", ondelete="CASCADE"), index=True
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[ent.HarnessSessionStatus] = mapped_column(
        SAEnum(ent.HarnessSessionStatus, name="harness_session_status"),
        nullable=False,
        default=ent.HarnessSessionStatus.ACTIVE,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(64), nullable=False, default="recon")
    model_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    state_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    engagement: Mapped[EngagementRow | None] = relationship(back_populates="harness_sessions")
    steps: Mapped[list[HarnessStepRow]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="HarnessStepRow.ordinal",
    )


class HarnessStepRow(Base):
    __tablename__ = "harness_steps"

    id: Mapped[UUID] = mapped_column(UUIDString(), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        UUIDString(),
        ForeignKey("harness_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    arguments_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[ent.HarnessStepStatus] = mapped_column(
        SAEnum(ent.HarnessStepStatus, name="harness_step_status"),
        nullable=False,
        default=ent.HarnessStepStatus.PENDING,
        index=True,
    )
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    recommended_model_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_summary: Mapped[str | None] = mapped_column(Text)
    tool_invocation_id: Mapped[UUID | None] = mapped_column(
        UUIDString(), ForeignKey("tool_invocations.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[HarnessSessionRow] = relationship(back_populates="steps")


# ---------------------------------------------------------------------------
# Engine factory + session helpers
# ---------------------------------------------------------------------------


DEFAULT_ENGAGEMENTS_ROOT = Path(
    os.environ.get("KESTREL_DATA_DIR", "~/.kestrel/engagements")
).expanduser()


def db_path_for_engagement(slug: str, root: Path | None = None) -> Path:
    """Return the expected on-disk path for an engagement's SQLite file."""

    base = (root or DEFAULT_ENGAGEMENTS_ROOT) / slug
    base.mkdir(parents=True, exist_ok=True)
    return base / "engagement.db"


def make_engine(url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    ``url`` examples::

        sqlite+aiosqlite:///path/to/engagement.db
        postgresql+asyncpg://user:pass@host/db

    If ``url`` is ``None``, a shared in-memory SQLite engine is created
    (useful for tests).
    """

    if url is None:
        url = "sqlite+aiosqlite:///:memory:"
    return create_async_engine(url, echo=echo, future=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_all(engine: AsyncEngine) -> None:
    """Create every table known to :class:`Base`.

    Intended for tests / first-run bootstrap. Production uses Alembic migrations.
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def open_session(
    sessionmaker_: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a committed-on-success, rolled-back-on-error transaction.

    Services use this via their constructor rather than opening sessions
    themselves.
    """

    async with sessionmaker_() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


__all__ = [
    "ArtifactRow",
    "Base",
    "CredentialRow",
    "DEFAULT_ENGAGEMENTS_ROOT",
    "EngagementRow",
    "FindingRow",
    "HarnessSessionRow",
    "HarnessStepRow",
    "ScopeEntryRow",
    "ScopeRow",
    "SessionRow",
    "TargetRow",
    "ToolInvocationRow",
    "UUIDString",
    "create_all",
    "db_path_for_engagement",
    "make_engine",
    "make_sessionmaker",
    "open_session",
]
