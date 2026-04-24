"""Internal firepower edition defaults for trusted crew operations.

This preset is intentionally separate from ``team`` so a private crew can opt
into the full tool surface without changing the safer Team MVP defaults.
"""

from __future__ import annotations

from kestrel_mcp.features import FeatureFlags

INTERNAL_DEFAULTS = FeatureFlags(
    scope_enforcement="warn_only",
    rate_limit_enabled=False,
    credential_encryption_required=False,
)
