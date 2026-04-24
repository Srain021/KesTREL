"""Tool catalog helpers shared by MCP, CLI, resources, and HARNESS."""

from __future__ import annotations

from collections.abc import Iterable

from .config import Settings
from .tools.base import ToolSpec

_HARNESS_PREFIXES = (
    "engagement_",
    "scope_",
    "target_",
    "finding_",
    "harness_",
)


def should_advertise(spec: ToolSpec, settings: Settings) -> bool:
    """Return whether ``spec`` should be shown to the LLM host."""

    if settings.llm.tool_exposure == "all":
        return True
    if spec.name.startswith(_HARNESS_PREFIXES):
        return True
    tags = set(spec.tags)
    return bool(tags & {"workflow", "readiness", "report"})


def advertised_specs(specs: Iterable[ToolSpec], settings: Settings) -> list[ToolSpec]:
    return [spec for spec in specs if should_advertise(spec, settings)]


def render_description(spec: ToolSpec, settings: Settings) -> str:
    return spec.render_description(settings.llm.tool_description_mode)


def catalog_payload(specs: Iterable[ToolSpec], settings: Settings) -> dict[str, object]:
    visible = advertised_specs(specs, settings)
    return {
        "tool_description_mode": settings.llm.tool_description_mode,
        "tool_exposure": settings.llm.tool_exposure,
        "model_tier": settings.llm.model_tier,
        "count": len(visible),
        "tools": [spec.catalog_metadata() for spec in visible],
    }

