"""Cross-cutting runtime infrastructure shared by every user-facing layer.

Members:
    * :mod:`.services`  — ``ServiceContainer``: constructed once per DB
    * :mod:`.context`   — ``RequestContext``: per-call state bound via ``contextvars``

Consumers (MCP server, FastAPI app, Textual TUI) build one
:class:`~.services.ServiceContainer` at startup and then open a
:class:`~.context.RequestContext` around every individual tool call / HTTP
request / key press that needs engagement-scoped services.

Design principle: this package contains **no business logic**. Business
rules live in :mod:`kestrel_mcp.domain.services`. This package just wires
infrastructure.
"""

from __future__ import annotations

from .context import (
    RequestContext,
    bind_context,
    current_context,
    current_context_or_none,
)
from .services import ServiceContainer

__all__ = [
    "RequestContext",
    "ServiceContainer",
    "bind_context",
    "current_context",
    "current_context_or_none",
]
