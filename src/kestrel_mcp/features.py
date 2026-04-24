"""Feature flags controlling runtime behavior across editions.

Every flag has a default compatible with Pro (strict) edition. Team and
internal edition presets override the unsafe-for-prod defaults.

See PRODUCT_LINES.md Part 9 for the decisions baked in here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ScopeEnforcement = Literal["strict", "warn_only", "off"]
_DEPRECATED_FIELDS = frozenset(
    {
        "cost_ledger",
        "tool_soft_timeout_enabled",
        "untrust_wrap_tool_output",
    }
)


class FeatureFlags(BaseModel):
    """Runtime-toggleable behavior flags. Immutable after Settings load."""

    scope_enforcement: ScopeEnforcement = Field(
        default="strict",
        description="How to handle out-of-scope targets. "
        "strict=block, warn_only=log+allow, off=silent.",
    )
    rate_limit_enabled: bool = Field(
        default=True,
        description="If False, RateLimiter.acquire() is a no-op.",
    )
    credential_encryption_required: bool = Field(
        default=True,
        description="If False, CredentialService allows plaintext values.",
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_deprecated_fields(cls, data: Any) -> Any:
        """Ignore known removed flags while still rejecting unknown extras.

        This keeps older YAML/env configurations bootable after the field
        cleanup, without weakening validation for truly unknown keys.
        """

        if not isinstance(data, Mapping):
            return data
        return {key: value for key, value in data.items() if key not in _DEPRECATED_FIELDS}

    model_config = {"extra": "forbid", "frozen": True}
