"""CLI entry point: ``python -m kestrel_mcp`` or ``kestrel``.

Subcommands:
    serve         Run the MCP server over stdio (default).
    doctor        Check tool binaries + API keys and print a readiness report.
    list-tools    Print the JSON MCP tool schema for inspection.
    version       Print package version.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import USER_CONFIG_DIR, load_settings
from .logging import configure_logging

app = typer.Typer(
    name="kestrel",
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
            help="Edition preset to load: 'pro' (default), 'team', or 'internal'.",
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

    settings = load_settings(config, edition=_edition_state["value"])
    if scope:
        settings.security.authorized_scope = [s.strip() for s in scope.split(",") if s.strip()]
    if dry_run:
        settings.security.dry_run = True

    configure_logging(
        level=settings.logging.level,
        log_dir=settings.expanded_path(settings.logging.dir) if settings.logging.dir else None,
        json_mode=settings.logging.format == "json",
    )

    from .server import run_sync

    run_sync(settings)


@app.command("serve-http")
def serve_http(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to an alternative YAML config file."),
    ] = None,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind address. Keep 127.0.0.1 behind a reverse proxy."),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Bind port.")] = 8765,
    endpoint: Annotated[
        str,
        typer.Option("--endpoint", help="Streamable HTTP MCP endpoint path."),
    ] = "/mcp",
    token_env: Annotated[
        str,
        typer.Option("--token-env", help="Environment variable holding the Bearer token."),
    ] = "KESTREL_MCP_HTTP_TOKEN",
    allow_no_auth: Annotated[
        bool,
        typer.Option("--allow-no-auth", help="Allow unauthenticated HTTP MCP traffic."),
    ] = False,
    json_response: Annotated[
        bool,
        typer.Option("--json-response", help="Prefer JSON responses instead of SSE streams."),
    ] = False,
    stateless: Annotated[
        bool,
        typer.Option("--stateless", help="Create a fresh MCP transport for every request."),
    ] = False,
    allowed_host: Annotated[
        list[str] | None,
        typer.Option(
            "--allowed-host", help="Allowed Host header when DNS rebinding protection is on."
        ),
    ] = None,
    allowed_origin: Annotated[
        list[str] | None,
        typer.Option(
            "--allowed-origin", help="Allowed Origin header when DNS rebinding protection is on."
        ),
    ] = None,
    dns_rebinding_protection: Annotated[
        bool,
        typer.Option(
            "--dns-rebinding-protection",
            help="Enable MCP SDK DNS rebinding checks; set allowed hosts for proxy domains.",
        ),
    ] = False,
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Comma-separated authorized scope override."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Do not actually run any offensive action."),
    ] = False,
) -> None:
    """Run MCP over Streamable HTTP for reverse-proxied team access.

    Local stdio access is unchanged; this is a second transport intended for
    Caddy/Nginx/Tailscale/Cloudflare Tunnel in front of localhost.
    """

    settings = load_settings(config, edition=_edition_state["value"])
    if scope:
        settings.security.authorized_scope = [s.strip() for s in scope.split(",") if s.strip()]
    if dry_run:
        settings.security.dry_run = True

    token = os.environ.get(token_env)
    if not token and not allow_no_auth:
        console.print(
            f"[red]Missing {token_env}.[/red] Set a Bearer token env var or pass --allow-no-auth "
            "for a strictly local lab."
        )
        raise typer.Exit(2)

    from .http_server import run_http_sync

    run_http_sync(
        settings,
        host=host,
        port=port,
        endpoint=endpoint,
        token=token,
        json_response=json_response,
        stateless=stateless,
        allowed_hosts=allowed_host or [],
        allowed_origins=allowed_origin or [],
        enable_dns_rebinding_protection=dns_rebinding_protection,
    )


@app.command()
def doctor() -> None:
    """Inspect installed tools + config and render a readiness table."""

    settings = load_settings(edition=_edition_state["value"])
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
    env_table.add_row("kestrel-mcp", __version__)
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

    settings = load_settings(edition=_edition_state["value"])
    configure_logging(level="WARNING", json_mode=False)

    from .harness import HarnessModule
    from .security import ScopeGuard
    from .tool_catalog import advertised_specs, render_description
    from .tools import load_modules
    from .workflows import load_workflow_specs

    scope_guard = ScopeGuard(settings.security.authorized_scope)
    modules = load_modules(settings, scope_guard)

    payload: list[dict[str, object]] = []
    specs_by_name = {spec.name: (module.id, spec) for module in modules for spec in module.specs()}
    for wf_spec in load_workflow_specs(settings, scope_guard):
        specs_by_name[wf_spec.name] = ("workflow", wf_spec)
    harness = HarnessModule(
        settings,
        scope_guard,
        specs_provider=lambda: {name: spec for name, (_module, spec) in specs_by_name.items()},
    )
    for harness_spec in harness.specs():
        specs_by_name[harness_spec.name] = ("harness", harness_spec)

    visible_names = {
        spec.name
        for spec in advertised_specs((spec for _module, spec in specs_by_name.values()), settings)
    }
    for name in sorted(specs_by_name):
        if name not in visible_names:
            continue
        module_id, spec = specs_by_name[name]
        payload.append(
            {
                "module": module_id,
                "name": spec.name,
                "description_short": spec.description,
                "description_full": render_description(spec, settings),
                "dangerous": spec.dangerous,
                "tags": spec.tags,
                "input_schema": spec.input_schema,
                "phase": spec.phase,
                "complexity_tier": spec.complexity_tier,
                "preferred_model_tier": spec.preferred_model_tier,
                "soft_timeout_sec": spec.soft_timeout_sec,
                "output_trust": spec.output_trust,
                "when_to_use": spec.when_to_use,
                "when_not_to_use": spec.when_not_to_use,
                "prerequisites": spec.prerequisites,
                "follow_ups": spec.follow_ups,
                "pitfalls": spec.pitfalls,
                "example_conversation": spec.example_conversation,
                "local_model_hints": spec.local_model_hints,
            }
        )

    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


@app.command("show-config")
def show_config_cmd() -> None:
    """Print resolved Settings (edition + features) as JSON."""

    s = load_settings(edition=_edition_state["value"])
    enabled_tools = sorted(
        name for name, block in s.tools.model_dump().items() if block.get("enabled")
    )
    payload = {
        "edition": s.edition,
        "features": s.features.model_dump(),
        "llm": s.llm.model_dump(),
        "enabled_tools": enabled_tools,
    }
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
    default_name = "nxc" if tool_name == "netexec" else tool_name
    if hint:
        p = Path(os.path.expanduser(hint))
        if p.is_file():
            return str(p)
        if found := shutil.which(hint):
            return found
        return None
    return shutil.which(default_name)


def _status_for(name: str, block: dict[str, Any], resolved: str | None) -> str:
    if not block.get("enabled"):
        return "[dim]disabled[/dim]"
    if name == "shodan":
        return (
            "[green]ready[/green]"
            if os.environ.get("SHODAN_API_KEY")
            else "[red]missing API key[/red]"
        )
    if name == "impacket":
        return (
            "[green]ready (python module)[/green]"
            if importlib.util.find_spec("impacket")
            else "[red]missing Python package[/red]"
        )
    if resolved:
        return "[green]ready[/green]"
    return "[red]binary not found[/red]"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
