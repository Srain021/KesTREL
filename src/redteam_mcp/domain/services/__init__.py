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

from .engagement_service import EngagementService
from .scope_service import ScopeService
from .target_service import TargetService
from .finding_service import FindingService

__all__ = [
    "EngagementService",
    "FindingService",
    "ScopeService",
    "TargetService",
]
