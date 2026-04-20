"""CLI entry point: ``python -m redteam_mcp`` or ``redteam-mcp``.

Subcommands:
    serve         Run the MCP server over stdio (default).
    doctor        Check tool binaries + API keys and print a readiness report.
    list-tools    Print the JSON MCP tool schema for inspection.
    version       Print package version.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import USER_CONFIG_DIR, load_settings
from .logging import configure_logging

app = typer.Typer(
    name="redteam-mcp",
    help="MCP server for red-team tooling (Shodan, Nuclei, Sliver, Havoc, Evilginx, Ligolo-ng, Caido).",
    add_completion=False,
    no_args_is_help=False,
)
console = Console(stderr=True)


_edition_state: dict[str, str | None] = {"value": None}


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    edition: Annotated[
        str | None,
        typer.Option(
            "--edition",
            help="Edition preset to load: 'pro' (default) or 'team'.",
            envvar="KESTREL_EDITION",
        ),
    ] = None,
) -> None:
    _edition_state["value"] = edition
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)


@app.command()
def serve(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to an alternative YAML config file."),
    ] = None,
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Comma-separated authorized scope override."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Do not actually run any offensive action."),
    ] = False,
) -> None:
    """Run the MCP server on stdio. Keep this process attached to the MCP host."""

    settings = load_settings(config)
    if scope:
        settings.security.authorized_scope = [s.strip() for s in scope.split(",") if s.strip()]
    if dry_run:
        settings.security.dry_run = True

    from .server import run_sync

    run_sync(settings)


@app.command()
def doctor() -> None:
    """Inspect installed tools + config and render a readiness table."""

    settings = load_settings()
    configure_logging(level="WARNING", json_mode=False)

    table = Table(title="Red-Team MCP — Tool Readiness", show_lines=True)
    table.add_column("Tool", style="cyan", no_wrap=True)
    table.add_column("Enabled")
    table.add_column("Binary", overflow="fold")
    table.add_column("Status")

    tools_cfg = settings.tools.model_dump()
    for name, block in tools_cfg.items():
        enabled = "✔" if block.get("enabled") else "✘"
        binary_hint = block.get("binary") or block.get("server_binary") or block.get("proxy_binary")
        resolved = _resolve_path(binary_hint, name)
        status = _status_for(name, block, resolved)
        table.add_row(name, enabled, str(resolved or "(not configured)"), status)

    console.print(table)

    console.print("\n[bold]Environment[/bold]")
    env_table = Table(show_header=False)
    env_table.add_row("Python", sys.version.split()[0])
    env_table.add_row("redteam-mcp", __version__)
    env_table.add_row("User config dir", str(USER_CONFIG_DIR))
    env_table.add_row(
        "Shodan API key",
        "present" if os.environ.get("SHODAN_API_KEY") else "[red]missing[/red]",
    )
    env_table.add_row(
        "Authorized scope",
        ", ".join(settings.security.authorized_scope)
        or "[red]EMPTY (offensive tools disabled)[/red]",
    )
    env_table.add_row("Dry-run mode", "on" if settings.security.dry_run else "off")
    console.print(env_table)


@app.command(name="list-tools")
def list_tools_cmd() -> None:
    """Dump the MCP tool schema as JSON (for debugging / integration)."""

    settings = load_settings()
    configure_logging(level="WARNING", json_mode=False)

    from .security import ScopeGuard
    from .tools import load_modules
    from .workflows import load_workflow_specs

    scope_guard = ScopeGuard(settings.security.authorized_scope)
    modules = load_modules(settings, scope_guard)

    payload: list[dict[str, object]] = []
    for module in modules:
        for spec in module.specs():
            payload.append(
                {
                    "module": module.id,
                    "name": spec.name,
                    "description_short": spec.description,
                    "description_full": spec.render_full_description(),
                    "dangerous": spec.dangerous,
                    "tags": spec.tags,
                    "input_schema": spec.input_schema,
                    "when_to_use": spec.when_to_use,
                    "when_not_to_use": spec.when_not_to_use,
                    "prerequisites": spec.prerequisites,
                    "follow_ups": spec.follow_ups,
                    "pitfalls": spec.pitfalls,
                    "example_conversation": spec.example_conversation,
                    "local_model_hints": spec.local_model_hints,
                }
            )

    for wf_spec in load_workflow_specs(settings, scope_guard):
        payload.append(
            {
                "module": "workflow",
                "name": wf_spec.name,
                "description_short": wf_spec.description,
                "description_full": wf_spec.render_full_description(),
                "dangerous": wf_spec.dangerous,
                "tags": wf_spec.tags,
                "input_schema": wf_spec.input_schema,
            }
        )

    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


@app.command("show-config")
def show_config_cmd() -> None:
    """Print resolved Settings (edition + features) as JSON."""

    from .config import Settings

    s = Settings.build(edition=_edition_state["value"])
    payload = {"edition": s.edition, "features": s.features.model_dump()}
    typer.echo(json.dumps(payload, indent=2))


team_app = typer.Typer(
    name="team",
    help="Team edition commands (use with --edition team).",
    no_args_is_help=True,
)
app.add_typer(team_app, name="team")


@team_app.command("bootstrap")
def team_bootstrap_cmd(
    name: Annotated[str, typer.Option("--name", "-n", help="Engagement slug.")],
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Comma-separated scope patterns."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview only; no DB writes."),
    ] = False,
) -> None:
    """Bootstrap a Team edition engagement in one command."""

    from .team.bootstrap import bootstrap

    edition = _edition_state.get("value") or "team"
    report = bootstrap(name=name, scope=scope, dry_run=dry_run, edition=edition)
    typer.echo(report.render())


@app.command()
def version() -> None:
    """Print the installed version."""

    typer.echo(__version__)


def _resolve_path(hint: str | None, tool_name: str) -> str | None:
    if hint:
        p = Path(os.path.expanduser(hint))
        if p.is_file():
            return str(p)
        if found := shutil.which(hint):
            return found
        return None
    return shutil.which(tool_name)


def _status_for(name: str, block: dict, resolved: str | None) -> str:
    if not block.get("enabled"):
        return "[dim]disabled[/dim]"
    if name == "shodan":
        return (
            "[green]ready[/green]"
            if os.environ.get("SHODAN_API_KEY")
            else "[red]missing API key[/red]"
        )
    if resolved:
        return "[green]ready[/green]"
    return "[red]binary not found[/red]"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
