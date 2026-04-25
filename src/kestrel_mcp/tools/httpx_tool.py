"""ProjectDiscovery httpx binary wrapper."""

from __future__ import annotations

import json
from typing import Any

from ..config import Settings
from ..domain import entities as ent
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class HttpxModule(ToolModule):
    id = "httpx"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.httpx
        self._binary_hint: str | None = getattr(block, "binary", None)

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "httpx")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="httpx_probe",
                description=(
                    "Probe in-scope hosts/URLs with ProjectDiscovery httpx and "
                    "return structured live HTTP metadata."
                ),
                input_schema={
                    "type": "object",
                    "required": ["targets"],
                    "properties": {
                        "targets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Hosts or URLs to probe.",
                        },
                        "tech_detect": {"type": "boolean", "default": True},
                        "status_code": {"type": "boolean", "default": True},
                        "title": {"type": "boolean", "default": True},
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 10,
                            "maximum": 1800,
                            "default": 300,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_probe,
                dangerous=True,
                requires_scope_field="targets",
                tags=["recon", "http", "active"],
                when_to_use=[
                    "User asks which subdomains are live over HTTP/HTTPS.",
                    "After subfinder_enum returns hostnames.",
                    "Before nuclei_scan, to reduce scan targets to live services.",
                ],
                when_not_to_use=[
                    "Target is out of authorized scope.",
                    "User only wants passive OSINT; httpx actively connects.",
                    "Input is a port range or CIDR; use nmap for service discovery.",
                ],
                prerequisites=[
                    "ProjectDiscovery httpx binary is installed or configured.",
                    "Every target is inside authorized_scope.",
                ],
                follow_ups=[
                    "Feed live URLs into nuclei_scan with critical/high filters.",
                    "Use page titles and tech tags to prioritize interesting hosts.",
                ],
                pitfalls=[
                    "Do not import Python httpx here; this wraps the Go binary.",
                    "Large target lists should go through stdin, not command-line args.",
                    "httpx may normalize hosts to URLs in the output.",
                ],
                local_model_hints=(
                    "Use this after subfinder. targets must be an array of hostnames or "
                    "URLs. Do not pass a comma-separated string."
                ),
            ),
            ToolSpec(
                name="httpx_version",
                description="Return the installed ProjectDiscovery httpx version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
                when_to_use=[
                    "Troubleshooting httpx probe failures.",
                    "User asks what httpx version is installed.",
                ],
                local_model_hints="Use this before suggesting binary install steps.",
            ),
        ]

    async def _handle_probe(self, arguments: dict[str, Any]) -> ToolResult:  # noqa: C901
        targets = [str(t).strip() for t in arguments["targets"] if str(t).strip()]
        for target in targets:
            await self.ensure_scope(target, tool_name="httpx_probe")

        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))

        argv = [binary, "-json", "-silent", "-no-color"]
        if bool(arguments.get("tech_detect", True)):
            argv.append("-td")
        if bool(arguments.get("status_code", True)):
            argv.append("-sc")
        if bool(arguments.get("title", True)):
            argv.append("-title")

        timeout = int(arguments.get("timeout_sec") or 300)
        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv, "targets": targets},
            )

        result = await run_command(
            argv,
            timeout_sec=timeout,
            max_output_bytes=self.settings.execution.max_output_bytes,
            stdin_data=("\n".join(targets) + "\n").encode("utf-8"),
        )
        probes = _parse_httpx_jsonl(result.stdout)

        target_ids: list[str] = []
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is not None and ctx.has_engagement():
                engagement_id = ctx.require_engagement()
                for probe in probes:
                    url = probe.get("url")
                    hostname = probe.get("target") or probe.get("host")
                    value = url if url else (hostname or "")
                    if not value:
                        continue
                    kind = ent.TargetKind.URL if url else ent.TargetKind.HOSTNAME
                    t = await ctx.target.add(
                        engagement_id=engagement_id,
                        kind=kind,
                        value=value,
                        discovered_by_tool="httpx_probe",
                    )
                    target_ids.append(str(t.id))
                    ports: list[int] = []
                    if url:
                        try:
                            from urllib.parse import urlparse

                            parsed = urlparse(url)
                            if parsed.port:
                                ports.append(parsed.port)
                            elif parsed.scheme == "https":
                                ports.append(443)
                            elif parsed.scheme == "http":
                                ports.append(80)
                        except Exception:  # noqa: BLE001
                            pass
                    tech = probe.get("tech") or []
                    hostnames = [hostname] if hostname else []
                    await ctx.target.update_enrichment(
                        t.id,
                        open_ports=ports or None,
                        tech_stack=tech if tech else None,
                        hostnames=hostnames if hostnames else None,
                    )
        except Exception as persist_exc:  # noqa: BLE001
            self.log.warning("httpx.persist_failed", error=str(persist_exc))

        audit_event(
            self.log,
            "httpx.probe",
            targets=len(targets),
            live=len(probes),
            exit_code=result.exit_code,
            duration_sec=result.duration_sec,
        )
        return ToolResult(
            text=f"httpx identified {len(probes)} live HTTP service(s).",
            structured={
                "targets": targets,
                "count": len(probes),
                "probes": probes,
                "exit_code": result.exit_code,
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
                "targets_created": target_ids,
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


def _parse_httpx_jsonl(text: str) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        probes.append(
            {
                "target": item.get("input") or item.get("host") or item.get("url"),
                "url": item.get("url"),
                "status_code": item.get("status-code"),
                "title": item.get("title"),
                "tech": item.get("tech") or [],
            }
        )
    return probes
