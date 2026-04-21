"""ProjectDiscovery subfinder wrapper."""

from __future__ import annotations

import json
from typing import Any

from ..config import Settings
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class SubfinderModule(ToolModule):
    id = "subfinder"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.subfinder
        self._binary_hint: str | None = getattr(block, "binary", None)

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "subfinder")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="subfinder_enum",
                description=(
                    "Enumerate subdomains for an in-scope domain using "
                    "ProjectDiscovery subfinder JSONL output."
                ),
                input_schema={
                    "type": "object",
                    "required": ["domain"],
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Apex domain to enumerate, e.g. example.com.",
                        },
                        "all_sources": {
                            "type": "boolean",
                            "default": False,
                            "description": "Use all sources, including slower ones.",
                        },
                        "silent": {
                            "type": "boolean",
                            "default": True,
                            "description": "Suppress banner/noise where supported.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 10,
                            "maximum": 1800,
                            "default": 300,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_enum,
                dangerous=True,
                requires_scope_field="domain",
                tags=["recon", "osint", "subdomains"],
                when_to_use=[
                    "User asks for passive subdomain enumeration.",
                    "Starting recon for a newly scoped apex domain.",
                    "Need hostnames to feed into httpx_probe or nuclei_scan.",
                ],
                when_not_to_use=[
                    "Target is an IP address or URL path, not a domain.",
                    "Scope is empty or does not include the apex domain.",
                    "User asked for active DNS brute force; subfinder is passive OSINT.",
                ],
                prerequisites=[
                    "subfinder binary is installed or configured in tools.subfinder.binary.",
                    "Domain is within authorized_scope.",
                ],
                follow_ups=[
                    "Run httpx_probe on returned hostnames to identify live HTTP services.",
                    "Run nuclei_scan only after live services are confirmed.",
                ],
                pitfalls=[
                    "ProjectDiscovery also ships httpx; keep binary config names distinct.",
                    "JSONL may include malformed/noisy lines; parser skips them.",
                    "all_sources=true can be slower and noisier.",
                ],
                local_model_hints=(
                    "Pass only the apex domain, not https:// URLs. If the user gives "
                    "https://app.example.com/path, extract example.com or ask whether "
                    "they want that specific host checked instead."
                ),
            ),
            ToolSpec(
                name="subfinder_version",
                description="Return the installed subfinder version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
                when_to_use=[
                    "Troubleshooting a missing or old subfinder install.",
                    "User asks what subfinder version is configured.",
                ],
                local_model_hints="Use this before suggesting a reinstall.",
            ),
        ]

    async def _handle_enum(self, arguments: dict[str, Any]) -> ToolResult:
        domain = str(arguments["domain"]).strip()
        self.scope_guard.ensure(domain, tool_name="subfinder_enum")

        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))

        argv = [binary, "-d", domain, "-json"]
        if bool(arguments.get("all_sources", False)):
            argv.append("-all")
        if bool(arguments.get("silent", True)):
            argv.append("-silent")

        timeout = int(arguments.get("timeout_sec") or 300)
        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv, "domain": domain},
            )

        result = await run_command(
            argv,
            timeout_sec=timeout,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        records = _parse_subfinder_jsonl(result.stdout)
        subdomains = sorted({r["host"] for r in records if r.get("host")})

        audit_event(
            self.log,
            "subfinder.enum",
            domain=domain,
            count=len(subdomains),
            exit_code=result.exit_code,
            duration_sec=result.duration_sec,
        )
        return ToolResult(
            text=f"subfinder found {len(subdomains)} subdomain(s) for {domain}.",
            structured={
                "domain": domain,
                "count": len(subdomains),
                "subdomains": subdomains,
                "records": records,
                "exit_code": result.exit_code,
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
            },
            is_error=not result.ok,
        )

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        result = await run_command([binary, "-version"], timeout_sec=30, max_output_bytes=64 * 1024)
        raw = (result.stdout or result.stderr).strip()
        return ToolResult(
            text=raw,
            structured={"raw": raw, "exit_code": result.exit_code},
            is_error=not result.ok,
        )


def _parse_subfinder_jsonl(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            host = item.get("host") or item.get("subdomain")
            if host:
                records.append(
                    {
                        "host": str(host),
                        "input": item.get("input"),
                        "source": item.get("source"),
                    }
                )
    return records
