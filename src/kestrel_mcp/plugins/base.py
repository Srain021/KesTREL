"""Plugin base class for third-party tool modules.

A plugin is a distributable Python package that registers additional
:class:`~kestrel_mcp.tools.base.ToolModule` instances without modifying
the core codebase.

Registration
------------

In ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."kestrel_mcp.plugins"]
    my_plugin = "my_plugin.kestral:MCPPlugin"

The entry-point value must be an importable callable or class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Settings
    from ..security import ScopeGuard
    from ..tools.base import ToolModule


class Plugin(ABC):
    """A third-party extension point for kestrel-mcp."""

    @abstractmethod
    def load_modules(
        self,
        settings: Settings,
        scope_guard: ScopeGuard,
    ) -> list[ToolModule]:
        """Return tool modules provided by this plugin.

        Implementations should respect ``settings`` — only return modules
        that are enabled/configured.
        """
