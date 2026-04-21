from __future__ import annotations

import os
import sys
from typing import Any, TypedDict, cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ... import __version__
from ...__main__ import _resolve_path, _status_for
from ...config import USER_CONFIG_DIR, Settings, load_settings
from ..templating import templates

router = APIRouter()


class ToolReadiness(TypedDict):
    name: str
    enabled: bool
    binary: str
    status: str


def _plain_rich_status(value: str) -> str:
    for token in ("[green]", "[red]", "[dim]", "[/green]", "[/red]", "[/dim]"):
        value = value.replace(token, "")
    return value


def _scope_entries(settings: Settings) -> list[str]:
    scope = settings.security.authorized_scope
    if isinstance(scope, str):
        return [entry.strip() for entry in scope.split(",") if entry.strip()]
    return list(scope)


def _build_tool_rows(settings: Settings) -> list[ToolReadiness]:
    tools_cfg = cast("dict[str, dict[str, Any]]", settings.tools.model_dump())
    rows: list[ToolReadiness] = []
    for name, block in tools_cfg.items():
        binary_hint = block.get("binary") or block.get("server_binary") or block.get("proxy_binary")
        binary = str(binary_hint) if binary_hint else None
        resolved = _resolve_path(binary, name)
        rows.append(
            {
                "name": name,
                "enabled": bool(block.get("enabled")),
                "binary": str(resolved or "(not configured)"),
                "status": _plain_rich_status(_status_for(name, block, resolved)),
            }
        )
    return rows


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    settings = load_settings()
    scope_entries = _scope_entries(settings)
    return templates.TemplateResponse(
        request,
        "settings/page.html.j2",
        {
            "active_engagement": None,
            "authorized_scope": ", ".join(scope_entries)
            or "EMPTY (offensive tools disabled)",
            "config_dir": str(USER_CONFIG_DIR),
            "edition": settings.edition,
            "python_version": sys.version.split()[0],
            "scope_count": len(scope_entries),
            "server_name": settings.server.name,
            "server_version": __version__,
            "shodan_key_status": "present" if os.environ.get("SHODAN_API_KEY") else "missing",
            "tools": _build_tool_rows(settings),
        },
    )
