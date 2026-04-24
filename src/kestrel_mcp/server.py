"""MCP server entry point.

Runs the kestrel-mcp server over stdio. Each incoming ``call_tool`` is
dispatched under a fresh :class:`~.core.context.RequestContext` so tool
handlers can look up the active engagement / scope / services without
threading them through every argument.

Responsibilities per request
----------------------------

1. Resolve the active engagement (from the server-level default, see below).
2. Construct a ``RequestContext`` and bind it to the task.
3. Run legacy scope guard checks AND persistent scope service checks.
4. Emit an audit event.
5. Dispatch to the tool handler and render the result.

Active-engagement resolution (tried in order)
---------------------------------------------

* ``arguments["_engagement"]``      MCP host may inject it
* ``settings.runtime.active_engagement_slug`` configured default
* environment ``KESTREL_ENGAGEMENT``
* ``None`` — legacy mode, uses the in-memory ScopeGuard only
"""

from __future__ import annotations

import json
import os
from typing import Any

import anyio

try:
    from mcp.server import Server  # type: ignore[import-not-found]
    from mcp.server.lowlevel.helper_types import ReadResourceContents  # type: ignore[import-not-found]
    from mcp.server.stdio import stdio_server  # type: ignore[import-not-found]
    from mcp.types import GetPromptResult, Prompt, PromptMessage, Resource, TextContent, Tool  # type: ignore[import-not-found]

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover
    Server = None  # type: ignore[assignment]
    ReadResourceContents = None  # type: ignore[misc,assignment]
    stdio_server = None  # type: ignore[assignment]
    GetPromptResult = None  # type: ignore[misc,assignment]
    Prompt = None  # type: ignore[misc,assignment]
    PromptMessage = None  # type: ignore[misc,assignment]
    TextContent = None  # type: ignore[assignment]
    Tool = None  # type: ignore[assignment]
    _MCP_AVAILABLE = False

from . import prompts as _prompts_module
from . import resources as _resources_module
from .config import Settings, load_settings
from .core import RequestContext, ServiceContainer
from .core.rate_limit import RateLimitedError, RateLimiter
from .domain.errors import ScopeViolationError
from .logging import audit_event, configure_logging, get_logger
from .security import AuthorizationError, ScopeGuard
from .tools import load_modules
from .tools.base import ToolResult, ToolSpec
from .workflows import load_workflow_specs


class RedTeamMCPServer:
    """Collects tool modules and exposes them through the MCP protocol."""

    def __init__(
        self,
        settings: Settings,
        *,
        container: ServiceContainer | None = None,
    ) -> None:
        if not _MCP_AVAILABLE:
            raise RuntimeError(
                "The 'mcp' Python package is not installed. "
                "Install it with: pip install 'mcp>=1.2.0'"
            )

        configure_logging(
            level=settings.logging.level,
            log_dir=settings.expanded_path(settings.logging.dir) if settings.logging.dir else None,
            json_mode=settings.logging.format == "json",
        )
        self.settings = settings
        self.log = get_logger("server")
        self.limiter = RateLimiter()

        # Legacy global scope guard (still consulted for tools that don't yet
        # integrate with RequestContext-driven scope).
        self.scope_guard = ScopeGuard(settings.security.authorized_scope)

        # New persistent service layer. When unavailable (no DB), runs in
        # legacy-only mode.
        self.container = container

        self.modules = load_modules(settings, self.scope_guard)

        self._specs: dict[str, ToolSpec] = {}
        for module in self.modules:
            for spec in module.specs():
                if spec.name in self._specs:
                    raise ValueError(f"Duplicate tool name {spec.name!r}")
                self._specs[spec.name] = spec

        for wf_spec in load_workflow_specs(settings, self.scope_guard):
            if wf_spec.name in self._specs:
                raise ValueError(f"Workflow collides with tool name {wf_spec.name!r}")
            self._specs[wf_spec.name] = wf_spec

        self.log.info(
            "server.init",
            tool_count=len(self._specs),
            modules=[m.id for m in self.modules],
            scope_count=len(settings.security.authorized_scope),
            dry_run=settings.security.dry_run,
            container=bool(container),
        )

    # ------------------------------------------------------------------

    def build(self) -> Any:
        """Construct and return the underlying ``mcp.server.Server``."""

        mcp = Server(self.settings.server.name, version=self.settings.server.version)

        @mcp.list_tools()  # type: ignore[misc]
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name=spec.name,
                    description=spec.render_full_description(),
                    inputSchema=spec.input_schema,
                )
                for spec in self._specs.values()
            ]

        @mcp.call_tool()  # type: ignore[misc]
        async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
            spec = self._specs.get(name)
            if spec is None:
                return [TextContent(type="text", text=f"ERROR: unknown tool {name!r}")]

            args = arguments or {}

            # Allow the host to explicitly override the engagement on a
            # per-call basis by injecting ``_engagement`` into arguments.
            call_engagement = args.pop("_engagement", None)

            async def _dispatch(ctx: RequestContext) -> ToolResult:
                from datetime import datetime, timezone

                started_at = datetime.now(timezone.utc)

                async def _record(result: ToolResult | None, error: Exception | None) -> None:
                    if not ctx.has_engagement():
                        return
                    completed_at = datetime.now(timezone.utc)
                    structured = result.structured if result is not None else {}
                    try:
                        from uuid import UUID

                        def _to_uuids(key: str) -> list[UUID]:
                            vals = structured.get(key) if isinstance(structured, dict) else None
                            if not isinstance(vals, list):
                                return []
                            out: list[UUID] = []
                            for v in vals:
                                try:
                                    out.append(UUID(str(v)))
                                except Exception:
                                    pass
                            return out

                        await ctx.tool_invocation.record(
                            engagement_id=ctx.require_engagement(),
                            actor_id=ctx.actor.id if ctx.actor else None,
                            tool_name=name,
                            arguments=args,
                            started_at=started_at,
                            completed_at=completed_at,
                            exit_code=0 if (result is not None and not result.is_error) else 1,
                            error_code=type(error).__name__ if error else None,
                            error_message=str(error) if error else None,
                            targets_created=_to_uuids("targets_created"),
                            findings_created=_to_uuids("findings_created"),
                            credentials_created=_to_uuids("credentials_created"),
                            artifacts_created=_to_uuids("artifacts_created"),
                        )
                    except Exception as record_exc:  # noqa: BLE001
                        self.log.warning(
                            "tool_invocation.record_failed",
                            tool=name,
                            error=str(record_exc),
                        )

                try:
                    await self._apply_rate_limit(ctx, name, spec)
                    if spec.requires_scope_field:
                        target = args.get(spec.requires_scope_field)
                        if isinstance(target, list):
                            for t in target:
                                await self._check_scope(ctx, str(t), name)
                        elif target is not None:
                            await self._check_scope(ctx, str(target), name)
                        elif spec.dangerous:
                            raise AuthorizationError(
                                f"Tool {name!r} requires a '{spec.requires_scope_field}' argument "
                                "for scope validation."
                            )

                    audit_event(
                        self.log,
                        f"tool.call.{name}",
                        name=name,
                        argument_keys=sorted(args.keys()),
                        dangerous=spec.dangerous,
                        engagement_id=str(ctx.engagement_id) if ctx.engagement_id else None,
                    )
                    result = await spec.handler(args)
                    await _record(result, None)
                    return result
                except Exception as exc:
                    await _record(None, exc)
                    raise

            try:
                result = await self._run_under_context(
                    call_engagement=call_engagement,
                    tool_name=name,
                    runner=_dispatch,
                )

            except (AuthorizationError, ScopeViolationError) as exc:
                self.log.warning("tool.auth_denied", tool=name, reason=str(exc))
                return [TextContent(type="text", text=f"AUTHORIZATION DENIED: {exc}")]
            except RateLimitedError as exc:
                self.log.warning(
                    "tool.rate_limited",
                    tool=name,
                    retry_after_sec=exc.retry_after_sec,
                )
                return [
                    TextContent(
                        type="text",
                        text=(
                            f"RATE LIMITED: Retry after {exc.retry_after_sec:.1f}s "
                            f"before calling {name!r} again."
                        ),
                    )
                ]
            except Exception as exc:  # noqa: BLE001
                self.log.exception("tool.unhandled_error", tool=name)
                return [TextContent(type="text", text=f"ERROR: {exc}")]

            return _render_result(result)

        @mcp.list_prompts()  # type: ignore[misc]
        async def list_prompts() -> list[Prompt]:
            return _prompts_module.list_prompts()

        @mcp.get_prompt()  # type: ignore[misc]
        async def get_prompt(name: str, arguments: dict[str, Any] | None = None) -> GetPromptResult:
            result = _prompts_module.get_prompt(name, arguments)
            if result is None:
                return GetPromptResult(
                    description="Prompt not found",
                    messages=[
                        PromptMessage(
                            role="assistant",
                            content=TextContent(type="text", text=f"Unknown prompt: {name!r}"),
                        )
                    ],
                )
            return result

        @mcp.list_resources()  # type: ignore[misc]
        async def list_resources() -> list[Resource]:
            async def _inner() -> list[Resource]:
                items = await _resources_module.list_all_resources()
                return [Resource(**item) for item in items]

            return await self._run_resource_under_context(_inner)

        @mcp.read_resource()  # type: ignore[misc]
        async def read_resource(uri: str) -> list[ReadResourceContents]:
            async def _inner() -> list[ReadResourceContents]:
                payload = await _resources_module.read_resource(uri)
                if payload is None:
                    return [
                        ReadResourceContents(
                            content="Resource not found.",
                            mime_type="text/plain",
                        )
                    ]
                return [
                    ReadResourceContents(
                        content=payload["text"],
                        mime_type=payload.get("mimeType"),
                    )
                ]

            return await self._run_resource_under_context(_inner)

        return mcp

    # ------------------------------------------------------------------

    async def _run_under_context(
        self,
        *,
        call_engagement: str | None,
        tool_name: str,
        runner,
    ) -> ToolResult:
        """Resolve engagement, bind a RequestContext, run the callback."""

        if self.container is None:
            # Legacy mode: fabricate a minimal context pointing at no engagement.
            from .core.context import RequestContext, bind_context

            fake_ctx = RequestContext(container=_NullContainer(), engagement_id=None)
            with bind_context(fake_ctx):
                return await runner(fake_ctx)

        engagement_id = await self._resolve_engagement(call_engagement)

        async with self.container.open_context(engagement_id=engagement_id) as ctx:
            return await runner(ctx)

    async def _run_resource_under_context(self, runner):
        """Bind a RequestContext for resource handlers (no tool-specific state)."""

        if self.container is None:
            from .core.context import RequestContext, bind_context

            fake_ctx = RequestContext(container=_NullContainer(), engagement_id=None)
            with bind_context(fake_ctx):
                return await runner()

        engagement_id = await self._resolve_engagement(None)

        async with self.container.open_context(engagement_id=engagement_id) as ctx:
            return await runner()

    async def _resolve_engagement(self, override: str | None):
        """Resolve the engagement id from override > settings > env > None."""

        if self.container is None:
            return None

        candidate = (
            override
            or getattr(self.settings, "runtime", None)
            and self.settings.runtime.active_engagement_slug  # type: ignore[union-attr]
            or os.environ.get("KESTREL_ENGAGEMENT")
        )
        if not candidate:
            return None

        # Candidate is a slug OR a UUID. Try slug first.
        try:
            from uuid import UUID

            return UUID(str(candidate))
        except ValueError:
            pass

        try:
            e = await self.container.engagement.get_by_name(str(candidate))
            return e.id
        except Exception:  # noqa: BLE001
            self.log.warning(
                "server.unknown_engagement",
                candidate=candidate,
                hint="Defaulting to no active engagement.",
            )
            return None

    # ------------------------------------------------------------------

    async def _apply_rate_limit(
        self,
        ctx: RequestContext,
        tool_name: str,
        spec: ToolSpec,
    ) -> None:
        """Apply per-tool rate limiting when the feature flag is enabled."""

        if not self.settings.features.rate_limit_enabled:
            return
        if spec.rate_limit is None:
            return

        engagement_key = str(ctx.engagement_id) if ctx.engagement_id is not None else "<none>"
        await self.limiter.acquire((tool_name, engagement_key), spec.rate_limit)

    # ------------------------------------------------------------------

    async def _check_scope(
        self,
        ctx: RequestContext,
        target: str,
        tool_name: str,
    ) -> None:
        """Central scope check, honoring ``FeatureFlags.scope_enforcement``.

        Precedence:
            1. If the context has an active engagement, the persistent
               :class:`ScopeService` is authoritative.
            2. Otherwise fall back to the in-memory :class:`ScopeGuard`
               (legacy mode / pre-engagement workflows).

        Feature-flag behavior (RFC-T00):

        * ``strict``    (Pro default): violations raise.
        * ``warn_only`` (Team default): violations logged and allowed.
        * ``off``       : no check at all.
        """

        enforcement = self.settings.features.scope_enforcement
        if enforcement == "off":
            return
        try:
            if ctx.has_engagement():
                await ctx.ensure_scope(target, tool_name=tool_name)
                return
            self.scope_guard.ensure(target, tool_name=tool_name)
        except (AuthorizationError, ScopeViolationError) as exc:
            if enforcement == "warn_only":
                self.log.warning(
                    "scope.warn_only",
                    tool=tool_name,
                    target=target,
                    reason=str(exc),
                    engagement_id=str(ctx.engagement_id) if ctx.engagement_id else None,
                )
                return
            raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_result(result: ToolResult) -> list[TextContent]:
    blocks: list[TextContent] = [TextContent(type="text", text=result.text)]
    if result.structured is not None:
        blocks.append(
            TextContent(
                type="text",
                text="```json\n" + json.dumps(result.structured, indent=2, default=str) + "\n```",
            )
        )
    return blocks


class _NullContainer:
    """Placeholder when the server runs without a ServiceContainer.

    Only the legacy scope-guard path is available; service attribute access
    raises so we catch accidental use.
    """

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(
            f"No ServiceContainer bound; '{name}' service is unavailable in legacy mode."
        )


async def serve(settings: Settings | None = None) -> None:
    """Run the server over stdio until the client disconnects."""

    settings = settings or load_settings()

    # Always try to attach a ServiceContainer; fall back silently on error so
    # legacy deployments still work.
    container: ServiceContainer | None = None
    try:
        container = ServiceContainer.default_on_disk(
            credential_encryption_required=settings.features.credential_encryption_required,
        )
        await container.initialise()
    except Exception as exc:  # noqa: BLE001
        get_logger("server").warning(
            "server.container_init_failed",
            error=str(exc),
            hint="Running in legacy mode (no engagement persistence).",
        )
        container = None

    server = RedTeamMCPServer(settings, container=container)
    mcp = server.build()

    try:
        async with stdio_server() as (reader, writer):
            await mcp.run(
                reader,
                writer,
                mcp.create_initialization_options(),
            )
    finally:
        if container is not None:
            await container.dispose()


def run_sync(settings: Settings | None = None) -> None:
    """Blocking entry point used by the CLI and tests."""

    anyio.run(serve, settings)
