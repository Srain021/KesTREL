"""Domain-layer exceptions.

Follows DEVELOPMENT_HANDBOOK.md §9 error taxonomy.
All domain errors inherit from :class:`DomainError`, which in turn is mapped
by the MCP / REST layer to user-facing ToolResult errors or HTTP 4xx/5xx.
"""

from __future__ import annotations

from ..core_errors import KestrelError


class DomainError(KestrelError):
    """Base class for all domain-layer errors."""

    error_code = "kestrel.domain"


class EngagementNotFoundError(DomainError):
    error_code = "kestrel.domain.engagement_not_found"
    user_actionable = True
    http_like_status = 404


class EngagementStateError(DomainError):
    """Operation disallowed in the engagement's current state (e.g. closed)."""

    error_code = "kestrel.domain.engagement_state"
    user_actionable = True
    http_like_status = 409


class InvalidStateTransitionError(DomainError):
    """Tried to move an entity to a state it cannot transition to."""

    error_code = "kestrel.domain.invalid_transition"
    user_actionable = True
    http_like_status = 409


class ScopeViolationError(DomainError):
    """An entity cannot be created because its target is out of scope."""

    error_code = "kestrel.domain.scope_violation"
    user_actionable = True
    http_like_status = 403


class UniqueConstraintError(DomainError):
    """Attempted to create a duplicate of a uniquely-keyed entity."""

    error_code = "kestrel.domain.unique"
    user_actionable = True
    http_like_status = 409


class CredentialSealError(DomainError):
    """Failed to encrypt/decrypt a credential (missing keyring, bad passphrase, etc.)."""

    error_code = "kestrel.domain.credential_seal"
    http_like_status = 500
