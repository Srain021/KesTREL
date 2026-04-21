"""Configuration-resolution tests — layered YAML + env override."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

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
