"""Base classes for Red-Team MCP tools.

Every concrete tool module inherits :class:`ToolModule` and exposes one or
more :class:`ToolSpec` entries. The server collects them, builds the MCP
``list_tools`` payload, and routes ``call_tool`` requests to the right
handler.

Design goals:
    * Tool authors write pure async Python; no MCP plumbing leakage.
    * Every tool declares an explicit JSON schema for its inputs.
    * Security checks (scope, dry-run, confirmation) are handled centrally
      rather than duplicated per tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from ..config import Settings
from ..domain.errors import ScopeViolationError
from ..logging import get_logger
from ..security import AuthorizationError, ScopeGuard

if TYPE_CHECKING:
    from ..core.rate_limit import RateLimitSpec

ToolHandler = Callable[[dict[str, Any]], Awaitable["ToolResult"]]
ToolPhase = Literal[
    "admin",
    "recon",
    "scan",
    "web",
    "ad",
    "c2",
    "post_exploit",
    "report",
    "workflow",
]
ModelTier = Literal["local", "standard", "strong"]
OutputTrust = Literal["safe", "untrusted", "sensitive"]


@dataclass
class ToolResult:
    """What a tool returns to the MCP layer.

    Structured + unstructured fields are both supported — structured output
    is surfaced via the MCP ``structuredContent`` field (for clients that
    support it) while ``text`` is the always-rendered human summary.
    """

    text: str
    structured: dict[str, Any] | None = None
    is_error: bool = False

    @classmethod
    def error(cls, message: str, **extra: Any) -> ToolResult:
        return cls(text=f"ERROR: {message}", structured={"error": message, **extra}, is_error=True)


@dataclass
class ToolSpec:
    """A single MCP tool advertised to clients.

    Extended description protocol
    -----------------------------

    Small / local LLMs (Qwen 7B, Llama-70B-Q4, Mistral 7B, DeepSeek 6.7B, etc.)
    cannot reliably infer tool usage from a one-line ``description`` + JSON
    schema. They mis-pick tools, fabricate arguments, or skip prerequisites.

    To compensate, every ToolSpec carries structured guidance that is later
    rendered into the MCP ``Tool.description`` field as tagged markdown
    sections. The structure is stable so that:

    * the server can pack it into MCP ``description`` (for generic hosts)
    * a future MCP Resource can expose the same data in JSON form
    * tests can assert each tool has the required sections filled

    Fields
    ------
    description
        The one-line purpose. Rendered first, before any structured block.

    when_to_use
        Bullet triggers. Short imperatives: "User asks X", "Target is Y".

    when_not_to_use
        Anti-patterns. Saves tokens avoiding wrong dispatch.

    prerequisites
        Hard preconditions. Tool would fail without these. E.g. "API key set".

    follow_ups
        What to do AFTER this tool returns, branching on likely outcomes.

    pitfalls
        Mistakes small LLMs typically make. One bullet per mistake.

    example_conversation
        A mini transcript of user ↔ agent using this tool correctly.

    local_model_hints
        Direct imperatives aimed at smaller models. "Do X. Don't Y." Blunt.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    dangerous: bool = False
    requires_scope_field: str | None = None
    tags: list[str] = field(default_factory=list)
    rate_limit: RateLimitSpec | None = None
    phase: ToolPhase = "admin"
    complexity_tier: int = 1
    preferred_model_tier: ModelTier = "standard"
    soft_timeout_sec: int | None = None
    output_trust: OutputTrust = "safe"

    # ---- Extended guidance (optional but STRONGLY recommended) ----
    when_to_use: list[str] = field(default_factory=list)
    when_not_to_use: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    example_conversation: str | None = None
    local_model_hints: str | None = None

    def render_compact_description(self) -> str:
        """Return the small-model catalog form.

        Detailed guidance stays available through ``tool://<name>/guide``.
        This keeps ``list_tools`` light for local models while preserving the
        full guidance as a single source of truth.
        """

        flags: list[str] = [f"phase={self.phase}", f"tier={self.complexity_tier}"]
        if self.dangerous:
            flags.append("dangerous")
        if self.tags:
            flags.append("tags=" + ",".join(self.tags[:4]))
        return f"{self.description.strip()} [{' ; '.join(flags)}]"

    def render_description(self, mode: str = "full") -> str:
        if mode == "compact":
            return self.render_compact_description()
        return self.render_full_description()

    def render_full_description(self) -> str:
        """Serialise the spec into a single description string for MCP.

        The output is plain text with section markers a model can scan. We
        deliberately use ASCII delimiters (``===``) instead of Markdown
        headings because some hosts strip ``#`` characters.
        """

        lines: list[str] = [self.description.strip()]

        if self.dangerous:
            lines.append(
                "\n[SAFETY] This tool performs an active or privileged action. "
                "Target scope is enforced automatically; out-of-scope calls are refused."
            )

        def _section(title: str, items: list[str]) -> None:
            if not items:
                return
            lines.append(f"\n=== {title} ===")
            for it in items:
                bullet = it.strip()
                if not bullet:
                    continue
                if not bullet.startswith(("-", "*", "•")):
                    bullet = "- " + bullet
                lines.append(bullet)

        _section("WHEN TO USE", self.when_to_use)
        _section("WHEN NOT TO USE", self.when_not_to_use)
        _section("PREREQUISITES", self.prerequisites)
        _section("FOLLOW-UPS", self.follow_ups)
        _section("PITFALLS", self.pitfalls)

        if self.example_conversation:
            lines.append("\n=== EXAMPLE ===")
            lines.append(self.example_conversation.strip())

        if self.local_model_hints:
            lines.append("\n=== LOCAL MODEL HINTS ===")
            lines.append(self.local_model_hints.strip())

        return "\n".join(lines).strip()

    def catalog_metadata(self) -> dict[str, Any]:
        """Stable metadata exposed via catalog resources and tests."""

        return {
            "name": self.name,
            "description": self.description,
            "dangerous": self.dangerous,
            "requires_scope_field": self.requires_scope_field,
            "tags": self.tags,
            "phase": self.phase,
            "complexity_tier": self.complexity_tier,
            "preferred_model_tier": self.preferred_model_tier,
            "soft_timeout_sec": self.soft_timeout_sec,
            "output_trust": self.output_trust,
        }


class ToolModule(ABC):
    """A group of related tools (e.g. all Shodan tools)."""

    #: Stable module identifier, used in config.tools.<id>.
    id: str = ""

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        self.settings = settings
        self.scope_guard = scope_guard
        self.log = get_logger(f"tool.{self.id}")

    @abstractmethod
    def specs(self) -> list[ToolSpec]:
        """Return the list of :class:`ToolSpec` this module exposes."""

    def enabled(self) -> bool:
        block = getattr(self.settings.tools, self.id, None)
        return bool(block and getattr(block, "enabled", False))

    async def ensure_scope(self, target: str, *, tool_name: str) -> None:
        """Validate ``target`` using the active request scope when available.

        The server already performs a central pre-dispatch check, but many
        handlers still keep a local guard for direct unit use and workflow
        reuse. This helper keeps that local guard aligned with the dynamic
        engagement DB scope instead of the startup-only config snapshot.
        """

        await ensure_target_scope(
            self.scope_guard,
            self.settings,
            self.log,
            target,
            tool_name=tool_name,
        )


async def ensure_target_scope(
    scope_guard: ScopeGuard,
    settings: Settings,
    log: Any,
    target: str,
    *,
    tool_name: str,
) -> None:
    """Shared scope helper for tools and workflows.

    Precedence mirrors :meth:`kestrel_mcp.server.RedTeamMCPServer._check_scope`:
    an active ``RequestContext`` uses the persistent engagement scope; otherwise
    legacy callers fall back to the in-memory ``ScopeGuard``.
    """

    enforcement = settings.features.scope_enforcement
    if enforcement == "off":
        return

    try:
        from ..core.context import current_context_or_none

        ctx = current_context_or_none()
        if ctx is not None and ctx.has_engagement():
            await ctx.ensure_scope(target, tool_name=tool_name)
            return
        scope_guard.ensure(target, tool_name=tool_name)
    except (AuthorizationError, ScopeViolationError) as exc:
        if enforcement == "warn_only":
            log.warning(
                "scope.warn_only",
                tool=tool_name,
                target=target,
                reason=str(exc),
            )
            return
        raise


async def target_in_scope(
    scope_guard: ScopeGuard,
    settings: Settings,
    log: Any,
    target: str,
    *,
    tool_name: str,
) -> bool:
    """Return whether ``target`` passes dynamic scope validation."""

    try:
        await ensure_target_scope(scope_guard, settings, log, target, tool_name=tool_name)
    except (AuthorizationError, ScopeViolationError):
        return False
    return True


def with_scope_check(
    spec_name: str,
    scope_guard: ScopeGuard,
    target_field: str,
) -> Callable[[ToolHandler], ToolHandler]:
    """Decorate a handler so it runs :meth:`ScopeGuard.ensure` first."""

    def decorator(handler: ToolHandler) -> ToolHandler:
        async def wrapped(arguments: dict[str, Any]) -> ToolResult:
            target = arguments.get(target_field)
            if target is None:
                return ToolResult.error(
                    f"Missing required field '{target_field}' for tool '{spec_name}'."
                )
            if isinstance(target, list):
                for item in target:
                    scope_guard.ensure(str(item), tool_name=spec_name)
            else:
                scope_guard.ensure(str(target), tool_name=spec_name)
            return await handler(arguments)

        return wrapped

    return decorator
