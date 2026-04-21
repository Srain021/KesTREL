"""Domain services — orchestrate persistence and business rules.

Service layer responsibilities (per DEVELOPMENT_HANDBOOK.md §9):

* Validate business invariants (state transitions, scope checks).
* Translate between entity (Pydantic) and row (ORM) types.
* Audit-log every mutation.
* Raise typed domain exceptions rather than leaking SQLAlchemy errors.

Services are **async** and accept a session maker, not a bound session.
This lets the server pick either a per-engagement SQLite or a shared
Postgres at runtime.
"""

from __future__ import annotations

from .credential_service import CredentialService
from .engagement_service import EngagementService
from .finding_service import FindingService
from .scope_service import ScopeService
from .target_service import TargetService

__all__ = [
    "CredentialService",
    "EngagementService",
    "FindingService",
    "ScopeService",
    "TargetService",
]
