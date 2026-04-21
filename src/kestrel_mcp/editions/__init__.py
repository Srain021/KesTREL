"""Edition presets for feature flags.

``get_defaults(name)`` returns the ``FeatureFlags`` instance appropriate for
the given edition. Used by ``Settings.build()``.
"""

from __future__ import annotations

from kestrel_mcp.editions.pro import PRO_DEFAULTS
from kestrel_mcp.editions.team import TEAM_DEFAULTS

__all__ = ["PRO_DEFAULTS", "TEAM_DEFAULTS", "get_defaults"]


def get_defaults(edition: str):
    if edition == "pro":
        return PRO_DEFAULTS
    if edition == "team":
        return TEAM_DEFAULTS
    raise ValueError(f"Unknown edition: {edition!r}. Expected 'pro' or 'team'.")
