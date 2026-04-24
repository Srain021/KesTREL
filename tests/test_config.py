"""Configuration-resolution tests — layered YAML + env override."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from kestrel_mcp.config import Settings, _deep_merge, load_settings


class TestDeepMerge:
    def test_simple(self) -> None:
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    def test_override_scalar(self) -> None:
        base = {"a": {"b": 1}}
        override = {"a": {"b": 99}}
        assert _deep_merge(base, override) == {"a": {"b": 99}}

    def test_list_replaces_not_merges(self) -> None:
        base = {"scope": ["a", "b"]}
        override = {"scope": ["c"]}
        assert _deep_merge(base, override) == {"scope": ["c"]}


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings()
        assert settings.server.name == "kestrel-mcp"
        assert settings.execution.timeout_sec == 300
        assert settings.security.authorized_scope == []
        assert settings.tools.shodan.enabled is True

    def test_env_override_security(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KESTREL_MCP_SECURITY__DRY_RUN", "true")
        monkeypatch.setenv("KESTREL_MCP_LOGGING__LEVEL", "debug")
        settings = Settings()
        assert settings.security.dry_run is True
        assert settings.logging.level == "DEBUG"

    def test_expanded_path(self) -> None:
        settings = Settings()
        p = settings.expanded_path("~/.kestrel/logs")
        assert str(p).startswith(str(Path.home()))

    def test_load_settings_with_explicit_file(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            """
security:
  authorized_scope: ["*.lab.test"]
tools:
  nuclei:
    enabled: false
""",
            encoding="utf-8",
        )
        os.environ.pop("KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE", None)
        settings = load_settings(cfg)
        assert settings.security.authorized_scope == ["*.lab.test"]
        assert settings.tools.nuclei.enabled is False

    def test_internal_edition_overlay_enables_all_tools(self, tmp_path: Path) -> None:
        cfg = tmp_path / "empty.yaml"
        cfg.write_text("", encoding="utf-8")

        settings = load_settings(cfg, edition="internal")

        assert settings.edition == "internal"
        assert settings.features.scope_enforcement == "warn_only"
        assert settings.features.rate_limit_enabled is False
        assert settings.tools.ffuf.enabled is True
        assert settings.tools.impacket.enabled is True
        assert settings.tools.bloodhound.enabled is True
        assert settings.tools.sliver.enabled is True

    def test_internal_edition_forces_firepower_but_preserves_tool_config(
        self,
        tmp_path: Path,
    ) -> None:
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            """
edition: internal
tools:
  ffuf:
    enabled: false
    wordlists_dir: "wordlists"
""",
            encoding="utf-8",
        )

        settings = load_settings(cfg)

        assert settings.edition == "internal"
        assert settings.tools.nmap.enabled is True
        assert settings.tools.ffuf.enabled is True
        assert settings.tools.ffuf.wordlists_dir == "wordlists"

    def test_legacy_feature_env_vars_are_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KESTREL_MCP_FEATURES__COST_LEDGER", "true")
        monkeypatch.setenv("KESTREL_MCP_FEATURES__TOOL_SOFT_TIMEOUT_ENABLED", "false")
        monkeypatch.setenv("KESTREL_MCP_FEATURES__UNTRUST_WRAP_TOOL_OUTPUT", "true")

        settings = Settings.build()

        assert settings.features.model_dump() == {
            "scope_enforcement": "strict",
            "rate_limit_enabled": True,
            "credential_encryption_required": True,
        }

    def test_unknown_feature_env_var_still_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KESTREL_MCP_FEATURES__NOT_A_REAL_FLAG", "true")

        with pytest.raises(ValidationError):
            Settings.build()
