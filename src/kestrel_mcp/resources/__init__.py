"""MCP Resources — dynamic context for the LLM host.

Resources are URI-addressable blobs that the host can fetch on demand.
Unlike tools, they are read-only and idempotent.
"""

from __future__ import annotations

import json
from typing import Any

from ..core.context import current_context_or_none

_RESOURCE_REGISTRY: dict[str, "ResourceProvider"] = {}


def register(
    provider: type["ResourceProvider"] | "ResourceProvider",
) -> type["ResourceProvider"] | "ResourceProvider":
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
