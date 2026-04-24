"""RequestContext — per-call engagement + actor + services.

Why ``contextvars``
-------------------

A single process may concurrently handle:

* a Cursor MCP request under engagement A
* a FastAPI HTTP request under engagement B
* a background task refreshing sessions

Passing a ``ctx`` argument through every tool handler is verbose and
error-prone. Thread-local state doesn't survive ``await`` points.
``contextvars.ContextVar`` is the Python-native answer: each asyncio task
carries its own ``RequestContext`` without the author thinking about it.

Usage
-----

.. code-block:: python

    async with container.open_context(engagement_id=eid, actor=alice) as ctx:
        # anywhere inside this block, possibly nested deeply:
        ctx2 = current_context()  # returns the same ctx
        await ctx.scope.ensure(ctx.engagement_id, "x.y", tool_name="t")

Nested contexts
---------------

``bind_context`` stacks: inner ``with`` supersedes outer; outer is
restored on exit. This lets workflows temporarily switch engagement.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from ..domain import entities as ent

if TYPE_CHECKING:
    from ..domain.services import (
        CredentialService,
        EngagementService,
        FindingService,
        HarnessService,
        ScopeService,
        TargetService,
        ToolInvocationService,
    )
    from .services import ServiceContainer


# Sentinel distinguishing "no context ever bound" from "context explicitly None".
_UNSET: RequestContext | None = None

_CTX: ContextVar[RequestContext | None] = ContextVar("kestrel_request_context", default=_UNSET)


class NoActiveEngagementError(Exception):
    """Raised when a tool handler requires an engagement but the context has none."""


class NoActiveContextError(Exception):
    """Raised when code requests the current context but none is bound.

    Almost always a server wiring bug. MCP tool handlers should never see
    this — the server guarantees a context before dispatch.
    """


@dataclass
class RequestContext:
    """State bound to one tool invocation."""

    container: ServiceContainer
    engagement_id: UUID | None = None
    actor: ent.Actor | None = None
    dry_run: bool = False

    # ---- convenience accessors to services ----

    @property
    def scope(self) -> ScopeService:
        return self.container.scope

    @property
    def engagement(self) -> EngagementService:
        return self.container.engagement

    @property
    def target(self) -> TargetService:
        return self.container.target

    @property
    def finding(self) -> FindingService:
        return self.container.finding

    @property
    def harness(self) -> HarnessService:
        return self.container.harness

    @property
    def credential(self) -> CredentialService:
        return self.container.credential

    @property
    def tool_invocation(self) -> ToolInvocationService:
        return self.container.tool_invocation

    # ---- engagement helpers ----

    def require_engagement(self) -> UUID:
        """Return the active engagement id or raise.

        Use inside handlers that mutate engagement data.
        """

        if self.engagement_id is None:
            raise NoActiveEngagementError(
                "This operation requires an active engagement. "
                "Call engagement_switch or engagement_activate first."
            )
        return self.engagement_id

    def has_engagement(self) -> bool:
        return self.engagement_id is not None

    # ---- scope convenience ----

    async def ensure_scope(self, target: str, *, tool_name: str) -> None:
        """Check a target against the active engagement's scope.

        No-op if there is no active engagement (the old global-scope path
        is expected to catch violations elsewhere — see
        :mod:`kestrel_mcp.security` fallback).
        """

        if self.engagement_id is None:
            return
        await self.scope.ensure(self.engagement_id, target, tool_name=tool_name)


# ---------------------------------------------------------------------------
# Binding helpers
# ---------------------------------------------------------------------------


@contextmanager
def bind_context(ctx: RequestContext) -> Iterator[RequestContext]:
    """Bind ``ctx`` as the active context for the duration of the ``with``.

    Safe for nesting; the previous binding is restored on exit.
    """

    token: Token[RequestContext | None] = _CTX.set(ctx)
    try:
        yield ctx
    finally:
        _CTX.reset(token)


def current_context() -> RequestContext:
    """Return the active :class:`RequestContext` or raise if none."""

    ctx = _CTX.get()
    if ctx is None:
        raise NoActiveContextError(
            "No RequestContext is bound in this task. "
            "Call inside a `container.open_context(...)` block."
        )
    return ctx


def current_context_or_none() -> RequestContext | None:
    """Return the active :class:`RequestContext` or ``None``.

    Useful for code paths that must run in both contextual and
    legacy / bootstrap modes.
    """

    return _CTX.get()


__all__ = [
    "NoActiveContextError",
    "NoActiveEngagementError",
    "RequestContext",
    "bind_context",
    "current_context",
    "current_context_or_none",
]
