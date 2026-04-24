"""Domain layer — business entities and services.

This layer defines WHAT the application is about (Engagement, Target, Finding,
Credential, Artifact, Session, ToolInvocation), independent of HOW the data is
stored or HOW users interact with it.

Public API (stable, versioned by semver):
    * Entity models (Pydantic)          — :mod:`.entities`
    * Domain services (business logic)  — :mod:`.services`
    * Exceptions                        — :mod:`.errors`

Consumers:
    * MCP server tool handlers
    * FastAPI REST endpoints (planned)
    * Textual TUI (planned)
    * CLI subcommands

Architectural rules:
    * Domain layer MUST NOT import from `tools/`, `workflows/`, or `server.py`.
    * Domain layer MAY import from `core/` (config, logging, security).
    * Persistence (SQLAlchemy) lives in :mod:`.storage`, isolated from entities.
    * All mutations go through services — never manipulate storage directly.
"""

from __future__ import annotations

from .entities import (
    Actor,
    ActorKind,
    Artifact,
    ArtifactKind,
    Confidence,
    Credential,
    CredentialKind,
    Engagement,
    EngagementStatus,
    EngagementType,
    EvidenceKind,
    Finding,
    FindingCategory,
    FindingEvidence,
    FindingSeverity,
    FindingStatus,
    Scope,
    ScopeEntry,
    ScopeEntryKind,
    Session,
    SessionKind,
    SessionStatus,
    Target,
    TargetKind,
    ToolInvocation,
)
from .errors import (
    DomainError,
    EngagementNotFoundError,
    EngagementStateError,
    InvalidStateTransitionError,
    ScopeViolationError,
)

__all__ = [
    # entities
    "Actor",
    "ActorKind",
    "Artifact",
    "ArtifactKind",
    "Confidence",
    "Credential",
    "CredentialKind",
    "Engagement",
    "EngagementStatus",
    "EngagementType",
    "EvidenceKind",
    "Finding",
    "FindingCategory",
    "FindingEvidence",
    "FindingSeverity",
    "FindingStatus",
    "Scope",
    "ScopeEntry",
    "ScopeEntryKind",
    "Session",
    "SessionKind",
    "SessionStatus",
    "Target",
    "TargetKind",
    "ToolInvocation",
    # errors
    "DomainError",
    "EngagementNotFoundError",
    "EngagementStateError",
    "InvalidStateTransitionError",
    "ScopeViolationError",
]
