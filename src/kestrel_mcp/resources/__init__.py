"""MCP Resources — dynamic context for the LLM host.

Resources are URI-addressable blobs that the host can fetch on demand.
Unlike tools, they are read-only and idempotent.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from ..core.context import current_context_or_none
from ..tool_catalog import catalog_payload
from ..tools.base import ToolSpec

_RESOURCE_REGISTRY: dict[str, ResourceProvider] = {}
_TOOL_SPECS: dict[str, ToolSpec] = {}
_TOOL_SETTINGS: Any | None = None


def configure_tool_catalog(specs: dict[str, ToolSpec], settings: Any) -> None:
    _TOOL_SPECS.clear()
    _TOOL_SPECS.update(specs)
    global _TOOL_SETTINGS
    _TOOL_SETTINGS = settings


def register(
    provider: type[ResourceProvider] | ResourceProvider,
) -> type[ResourceProvider] | ResourceProvider:
    """Register a resource provider by URI scheme."""

    instance = provider() if isinstance(provider, type) else provider
    scheme = instance.scheme.strip()
    if not scheme:
        raise ValueError("Resource provider must declare a non-empty scheme.")
    _RESOURCE_REGISTRY[scheme] = instance
    return provider


class ResourceProvider:
    """Pluggable source of MCP resources."""

    scheme: str = ""

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return metadata for resources this provider knows about."""

        return []

    async def read_resource(self, uri: str) -> dict[str, Any] | None:
        """Return the resource payload or None if not found."""

        return None


@register
class EngagementResourceProvider(ResourceProvider):
    scheme = "engagement"

    async def list_resources(self) -> list[dict[str, Any]]:
        ctx = current_context_or_none()
        if ctx is None or not ctx.has_engagement():
            return []
        eid = str(ctx.engagement_id)
        return [
            {
                "uri": f"engagement://{eid}/summary",
                "name": "Active Engagement Summary",
                "mimeType": "application/json",
                "description": "High-level metadata of the current engagement.",
            },
            {
                "uri": f"engagement://{eid}/scope",
                "name": "Engagement Scope",
                "mimeType": "application/json",
                "description": "Authorized scope entries for the engagement.",
            },
            {
                "uri": f"engagement://{eid}/targets",
                "name": "Engagement Targets",
                "mimeType": "application/json",
                "description": "Discovered targets (up to 50).",
            },
            {
                "uri": f"engagement://{eid}/findings",
                "name": "Engagement Findings",
                "mimeType": "application/json",
                "description": "Vulnerability findings (up to 50).",
            },
        ]

    async def read_resource(self, uri: str) -> dict[str, Any] | None:
        uri = str(uri)
        ctx = current_context_or_none()
        if ctx is None or not ctx.has_engagement():
            return None

        engagement_id = ctx.require_engagement()
        prefix = f"engagement://{engagement_id}/"
        if not uri.startswith(prefix):
            return None

        path = uri[len(prefix) :]
        try:
            if path == "summary":
                engagement = await ctx.engagement.get(engagement_id)
                if engagement is None:
                    return None
                return {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(
                        engagement.model_dump(mode="json", exclude_none=True), indent=2
                    ),
                }

            if path == "scope":
                scope = await ctx.scope.list_entries(engagement_id)
                return {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(
                        [s.model_dump(mode="json", exclude_none=True) for s in scope],
                        indent=2,
                    ),
                }

            if path == "targets":
                targets = await ctx.target.list_for_engagement(engagement_id)
                return {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(
                        [t.model_dump(mode="json", exclude_none=True) for t in targets[:50]],
                        indent=2,
                    ),
                }

            if path == "findings":
                findings = await ctx.finding.list_for_engagement(engagement_id)
                return {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(
                        [f.model_dump(mode="json", exclude_none=True) for f in findings[:50]],
                        indent=2,
                    ),
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "uri": uri,
                "mimeType": "text/plain",
                "text": f"Error reading resource: {exc}",
            }

        return None


@register
class ToolResourceProvider(ResourceProvider):
    scheme = "tool"

    async def list_resources(self) -> list[dict[str, Any]]:
        if not _TOOL_SPECS:
            return []
        return [
            {
                "uri": "tool://catalog",
                "name": "Tool Catalog",
                "mimeType": "application/json",
                "description": "Compact metadata for advertised tools.",
            },
            *[
                {
                    "uri": f"tool://{name}/guide",
                    "name": f"{name} Guide",
                    "mimeType": "text/markdown",
                    "description": "Full ToolSpec guidance for one tool.",
                }
                for name in sorted(_TOOL_SPECS)
            ],
        ]

    async def read_resource(self, uri: str) -> dict[str, Any] | None:
        if uri == "tool://catalog":
            if _TOOL_SETTINGS is None:
                return None
            return {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(
                    catalog_payload(_TOOL_SPECS.values(), _TOOL_SETTINGS),
                    indent=2,
                ),
            }
        if not uri.startswith("tool://") or not uri.endswith("/guide"):
            return None
        name = uri[len("tool://") : -len("/guide")]
        spec = _TOOL_SPECS.get(name)
        if spec is None:
            return None
        return {
            "uri": uri,
            "mimeType": "text/markdown",
            "text": spec.render_full_description(),
        }


@register
class HarnessResourceProvider(ResourceProvider):
    scheme = "harness"

    async def list_resources(self) -> list[dict[str, Any]]:
        return []

    async def read_resource(self, uri: str) -> dict[str, Any] | None:
        if not uri.startswith("harness://") or not uri.endswith("/state"):
            return None
        ctx = current_context_or_none()
        if ctx is None:
            return None
        raw = uri[len("harness://") : -len("/state")]
        try:
            session_id = UUID(raw)
        except ValueError:
            return None
        payload = await ctx.harness.get_state_payload(session_id)
        if payload is None:
            return None
        return {
            "uri": uri,
            "mimeType": "application/json",
            "text": json.dumps(payload, indent=2, default=str),
        }


async def list_all_resources() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for provider in _RESOURCE_REGISTRY.values():
        out.extend(await provider.list_resources())
    return out


async def read_resource(uri: str) -> dict[str, Any] | None:
    uri = str(uri)
    scheme, _sep, _rest = uri.partition("://")
    provider = _RESOURCE_REGISTRY.get(scheme)
    if provider is None:
        return None
    return await provider.read_resource(uri)
