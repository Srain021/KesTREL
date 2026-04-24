"""Plugin registry — dynamically load third-party tool modules.

Scanning happens via ``importlib.metadata.entry_points`` in the group
``kestrel_mcp.plugins``.  Every entry-point is loaded and expected to be
either:

    * a :class:`.base.Plugin` subclass (instantiated, then
      ``load_modules`` called), or
    * a plain callable that accepts ``(Settings, ScopeGuard)`` and returns
      a list of :class:`~kestrel_mcp.tools.base.ToolModule` instances.

Errors for individual entry-points are swallowed and logged so that a
broken plugin does not prevent the server from starting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from importlib.metadata import entry_points as _entry_points
except ImportError:  # pragma: no cover
    _entry_points = None  # type: ignore[misc,assignment]

from ..logging import get_logger

if TYPE_CHECKING:
    from ..config import Settings
    from ..security import ScopeGuard
    from ..tools.base import ToolModule

_log = get_logger("plugins")


def load_plugin_modules(settings: Settings, scope_guard: ScopeGuard) -> list[ToolModule]:
    """Return tool modules contributed by all registered plugins."""

    modules: list[ToolModule] = []
    if _entry_points is None:
        return modules

    try:
        eps = _entry_points()
        if hasattr(eps, "select"):
            group = eps.select(group="kestrel_mcp.plugins")
        else:
            group = eps.get("kestrel_mcp.plugins", [])
    except Exception as exc:  # noqa: BLE001
        _log.warning("plugin.entry_points_failed", error=str(exc))
        return modules

    for ep in group:
        try:
            loaded = ep.load()
        except Exception as exc:  # noqa: BLE001
            _log.warning("plugin.load_failed", name=ep.name, error=str(exc))
            continue

        try:
            from .base import Plugin

            if isinstance(loaded, type) and issubclass(loaded, Plugin):
                instance = loaded()
                discovered = instance.load_modules(settings, scope_guard)
            elif callable(loaded):
                discovered = loaded(settings, scope_guard)
            else:
                _log.warning("plugin.not_callable", name=ep.name, type=type(loaded).__name__)
                continue

            if isinstance(discovered, list):
                for m in discovered:
                    modules.append(m)
                _log.info(
                    "plugin.loaded",
                    name=ep.name,
                    modules=len(discovered),
                )
            else:
                _log.warning("plugin.bad_return", name=ep.name, type=type(discovered).__name__)
        except Exception as exc:  # noqa: BLE001
            _log.warning("plugin.init_failed", name=ep.name, error=str(exc))

    return modules
