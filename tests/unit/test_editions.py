"""Tests for RFC-A04 edition + FeatureFlags infrastructure."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kestrel_mcp.config import Settings
from kestrel_mcp.editions import PRO_DEFAULTS, TEAM_DEFAULTS, get_defaults
from kestrel_mcp.features import FeatureFlags


def test_feature_flags_frozen():
    ff = FeatureFlags()
    with pytest.raises((ValidationError, TypeError)):
        ff.rate_limit_enabled = False


def test_feature_flags_extra_forbidden():
    with pytest.raises(ValidationError):
        FeatureFlags(unknown_flag=True)  # type: ignore[call-arg]


def test_pro_defaults_are_strict():
    assert PRO_DEFAULTS.scope_enforcement == "strict"
    assert PRO_DEFAULTS.rate_limit_enabled is True
    assert PRO_DEFAULTS.credential_encryption_required is True
    assert PRO_DEFAULTS.tool_soft_timeout_enabled is True


def test_team_defaults_are_unleashed():
    assert TEAM_DEFAULTS.scope_enforcement == "warn_only"
    assert TEAM_DEFAULTS.rate_limit_enabled is False
    assert TEAM_DEFAULTS.credential_encryption_required is False
    assert TEAM_DEFAULTS.tool_soft_timeout_enabled is False
    assert TEAM_DEFAULTS.cost_ledger is True
    assert TEAM_DEFAULTS.untrust_wrap_tool_output is True


def test_get_defaults_unknown_edition_raises():
    with pytest.raises(ValueError):
        get_defaults("enterprise")


def test_settings_build_pro_is_default():
    s = Settings.build()
    assert s.edition == "pro"
    assert s.features.scope_enforcement == "strict"
    assert s.features.rate_limit_enabled is True


def test_settings_build_team():
    s = Settings.build(edition="team")
    assert s.edition == "team"
    assert s.features.scope_enforcement == "warn_only"
    assert s.features.rate_limit_enabled is False


def test_settings_build_env_override(monkeypatch):
    monkeypatch.setenv("KESTREL_EDITION", "team")
    s = Settings.build()
    assert s.edition == "team"
    assert s.features.scope_enforcement == "warn_only"


def test_settings_build_explicit_feature_override_wins():
    explicit = FeatureFlags(scope_enforcement="strict")
    s = Settings.build(edition="team", features=explicit)
    # Explicit override wins for the field it sets...
    assert s.features.scope_enforcement == "strict"
    # ...but other Team defaults are preserved.
    assert s.features.rate_limit_enabled is False


def test_settings_edition_field_rejects_unknown():
    # pydantic Literal["pro", "team"] rejects other values.
    with pytest.raises(ValidationError):
        Settings(edition="enterprise")  # type: ignore[arg-type]
