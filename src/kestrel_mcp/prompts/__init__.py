"""MCP Prompts (Phase 3+).

Predefined prompt templates the LLM can invoke, e.g.
    * ``pentest_kickoff``     Structured engagement intake form
    * ``ctf_recon_playbook``  Step-by-step recon for CTF boxes

Prompts are stored as plain Markdown files beside this module.  Each file
becomes a single :class:`mcp.types.Prompt` whose *name* is the filename
stem and whose *description* is drawn from the first H1 heading.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    from mcp.types import (  # type: ignore[import-not-found]
        GetPromptResult,
        Prompt,
        PromptMessage,
        TextContent,
    )

    _MCP_AVAILABLE = True
except ImportError:  # pragma: no cover
    GetPromptResult = None  # type: ignore[misc,assignment]
    Prompt = None  # type: ignore[misc,assignment]
    PromptMessage = None  # type: ignore[misc,assignment]
    TextContent = None  # type: ignore[misc,assignment]
    _MCP_AVAILABLE = False

_LOG = logging.getLogger(__name__)


def _prompts_dir() -> Path:
    return Path(__file__).parent


def _slugify_filename(name: str) -> str:
    """Return the filesystem stem for a given prompt *name*.

    We accept either the raw stem (``en_redteam_operator``) or a
    human-friendly variant (``en-redteam-operator``).
    """
    return name.replace("-", "_")


def list_prompts() -> list[Prompt]:
    """Scan the prompts directory and return metadata for every ``.md`` file."""

    if not _MCP_AVAILABLE:
        return []

    results: list[Prompt] = []
    for path in sorted(_prompts_dir().glob("*.md")):
        name = path.stem
        description = _extract_description(path)
        results.append(
            Prompt(
                name=name,
                description=description,
            )
        )
    return results


def get_prompt(name: str, arguments: dict[str, Any] | None = None) -> GetPromptResult | None:
    """Load the raw Markdown content for *name* and wrap it in a
    :class:`GetPromptResult`.

    Returns ``None`` when the prompt does not exist so the caller can decide
    whether to raise a 404-style error.
    """

    if not _MCP_AVAILABLE:
        return None

    slug = _slugify_filename(name)
    path = _prompts_dir() / f"{slug}.md"
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    return GetPromptResult(
        description=_extract_description(path),
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=content),
            )
        ],
    )


def _extract_description(path: Path) -> str:
    """Heuristic: first line that looks like an H1 heading, or the filename."""

    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped.startswith("## "):
                return stripped[3:].strip()
    except Exception:
        _LOG.warning("prompt.read_failed", path=str(path))

    return path.stem.replace("_", " ")
