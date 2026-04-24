"""Team edition defaults: unleashed mode for internal crew.

Decisions (see PRODUCT_LINES.md Part 9):
- scope_enforcement=warn_only  (crew self-regulates)
- rate_limit_enabled=False     (no throttling during ops)
- credential_encryption_required=False (shared plaintext OK inside vault)
"""

from __future__ import annotations

from kestrel_mcp.features import FeatureFlags

TEAM_DEFAULTS = FeatureFlags(
    scope_enforcement="warn_only",
    rate_limit_enabled=False,
    credential_encryption_required=False,
)
