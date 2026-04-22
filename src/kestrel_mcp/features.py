"""Feature flags controlling runtime behavior across editions.

Every flag has a default compatible with Pro (strict) edition. Team and
internal edition presets override the unsafe-for-prod defaults.

See PRODUCT_LINES.md Part 9 for the decisions baked in here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScopeEnforcement = Literal["strict", "warn_only", "off"]


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
    cost_ledger: bool = Field(
        default=True,
        description="If True, record estimated cost per ToolInvocation.",
    )
    tool_soft_timeout_enabled: bool = Field(
        default=True,
        description="If False, ToolSpec.soft_timeout_sec is ignored.",
    )
    untrust_wrap_tool_output: bool = Field(
        default=True,
        description="If True, wrap ToolResult with <untrusted>...</untrusted>.",
    )

    model_config = {"extra": "forbid", "frozen": True}
