"""Tests for the plugin registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.plugins import load_plugin_modules
from kestrel_mcp.plugins.base import Plugin
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.base import ToolModule, ToolSpec


class FakeToolModule(ToolModule):
    id = "fake_plugin_tool"

    def specs(self) -> list[ToolSpec]:
        return []


class DummyPlugin(Plugin):
    def load_modules(self, settings: Settings, scope_guard: ScopeGuard) -> list[ToolModule]:
        return [FakeToolModule(settings, scope_guard)]


@pytest.fixture
def settings() -> Settings:
    return Settings.build()


@pytest.fixture
def scope_guard(settings: Settings) -> ScopeGuard:
    return ScopeGuard(settings.security.authorized_scope)


def test_no_plugins_returns_empty(settings: Settings, scope_guard: ScopeGuard) -> None:
    with patch("kestrel_mcp.plugins._entry_points", side_effect=ImportError):
        modules = load_plugin_modules(settings, scope_guard)
    assert modules == []


def test_plugin_subclass_loaded(settings: Settings, scope_guard: ScopeGuard) -> None:
    mock_ep = MagicMock()
    mock_ep.name = "dummy"
    mock_ep.load.return_value = DummyPlugin

    mock_eps = MagicMock()
    mock_eps.select.return_value = [mock_ep]

    with patch("kestrel_mcp.plugins._entry_points", return_value=mock_eps):
        modules = load_plugin_modules(settings, scope_guard)

    assert len(modules) == 1
    assert isinstance(modules[0], FakeToolModule)


def test_callable_plugin_loaded(settings: Settings, scope_guard: ScopeGuard) -> None:
    def make_modules(settings: Settings, scope_guard: ScopeGuard) -> list[ToolModule]:
        return [FakeToolModule(settings, scope_guard)]

    mock_ep = MagicMock()
    mock_ep.name = "callable"
    mock_ep.load.return_value = make_modules

    mock_eps = MagicMock()
    mock_eps.select.return_value = [mock_ep]

    with patch("kestrel_mcp.plugins._entry_points", return_value=mock_eps):
        modules = load_plugin_modules(settings, scope_guard)

    assert len(modules) == 1


def test_broken_plugin_skipped(settings: Settings, scope_guard: ScopeGuard) -> None:
    mock_ep = MagicMock()
    mock_ep.name = "broken"
    mock_ep.load.side_effect = RuntimeError("bad import")

    mock_eps = MagicMock()
    mock_eps.select.return_value = [mock_ep]

    with patch("kestrel_mcp.plugins._entry_points", return_value=mock_eps):
        modules = load_plugin_modules(settings, scope_guard)

    assert modules == []
