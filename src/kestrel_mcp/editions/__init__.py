"""Edition presets for feature flags.

``get_defaults(name)`` returns the ``FeatureFlags`` instance appropriate for
the given edition. Used by ``Settings.build()``.
"""

from __future__ import annotations

from kestrel_mcp.editions.internal import INTERNAL_DEFAULTS
from kestrel_mcp.editions.pro import PRO_DEFAULTS
from kestrel_mcp.editions.team import TEAM_DEFAULTS
from kestrel_mcp.features import FeatureFlags

__all__ = ["INTERNAL_DEFAULTS", "PRO_DEFAULTS", "TEAM_DEFAULTS", "get_defaults"]


def get_defaults(edition: str) -> FeatureFlags:
    if edition == "pro":
        return PRO_DEFAULTS
    if edition == "team":
        return TEAM_DEFAULTS
    if edition == "internal":
        return INTERNAL_DEFAULTS
    raise ValueError(f"Unknown edition: {edition!r}. Expected 'pro', 'team', or 'internal'.")
