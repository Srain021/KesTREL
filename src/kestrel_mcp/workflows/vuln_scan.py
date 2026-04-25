"""Full vulnerability scan workflow.

Chains:
    1. nmap_scan  — discover open ports and services
    2. httpx_probe — identify live HTTP services
    3. nuclei_scan — vulnerability scan against live targets
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..logging import audit_event, get_logger
from ..security import ScopeGuard
from ..tools.base import (
    ToolHandler,
    ToolResult,
    ToolSpec,
    ensure_target_scope,
    target_in_scope,
)


class FullVulnScanWorkflow:
    """Build the ``full_vuln_scan`` tool spec."""

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        self.settings = settings
        self.scope_guard = scope_guard
        self.log = get_logger("workflow.vuln_scan")

    def spec(  # noqa: C901
        self,
        *,
        nmap_scan: ToolHandler,
        httpx_probe: ToolHandler,
        nuclei_scan: ToolHandler,
    ) -> ToolSpec:
        async def handler(arguments: dict[str, Any]) -> ToolResult:  # noqa: C901
            targets = [str(t).strip() for t in arguments["targets"] if str(t).strip()]
            for target in targets:
                await ensure_target_scope(
                    self.scope_guard,
                    self.settings,
                    self.log,
                    target,
                    tool_name="full_vuln_scan",
                )

            ports = str(arguments.get("ports") or "1-1024")
            severity = arguments.get("severity", ["critical", "high", "medium"])
            timing = int(arguments.get("timing", 3))
            timeout_sec = int(arguments.get("timeout_sec") or 600)

            audit_event(
                self.log,
                "vuln_scan.start",
                targets=len(targets),
                ports=ports,
            )

            # 1. Nmap discovery
            nmap_result = await nmap_scan(
                {
                    "targets": targets,
                    "ports": ports,
                    "timing": timing,
                    "timeout_sec": timeout_sec,
                }
            )
            if nmap_result.is_error:
                return ToolResult(
                    text=f"Nmap scan failed: {nmap_result.text}",
                    structured={"stage": "nmap", "error": nmap_result.text},
                    is_error=True,
                )

            hosts = (nmap_result.structured or {}).get("hosts", [])
            all_web_targets: list[str] = []
            for host in hosts:
                addr = host.get("address")
                if not addr:
                    continue
                for port_info in host.get("ports", []):
                    port = port_info.get("port")
                    proto = port_info.get("protocol", "tcp")
                    state = port_info.get("state")
                    service = port_info.get("service", "")
                    if state != "open" or proto != "tcp":
                        continue
                    if port in (80, 8080, 8000, 3000):
                        all_web_targets.append(f"http://{addr}:{port}")
                    elif port in (443, 8443):
                        all_web_targets.append(f"https://{addr}:{port}")
                    elif service in ("http", "https"):
                        scheme = "https" if port == 443 else "http"
                        all_web_targets.append(f"{scheme}://{addr}:{port}")

            all_web_targets = list(dict.fromkeys(all_web_targets))

            # 2. httpx_probe (optional but recommended for Nuclei)
            live_targets: list[str] = []
            if all_web_targets:
                in_scope_web = []
                for wt in all_web_targets:
                    if await target_in_scope(
                        self.scope_guard,
                        self.settings,
                        self.log,
                        wt,
                        tool_name="full_vuln_scan.httpx_filter",
                    ):
                        in_scope_web.append(wt)

                if in_scope_web:
                    httpx_result = await httpx_probe(
                        {
                            "targets": in_scope_web,
                            "tech_detect": True,
                            "status_code": True,
                            "title": True,
                            "timeout_sec": min(timeout_sec, 300),
                        }
                    )
                    if not httpx_result.is_error and httpx_result.structured:
                        probes = httpx_result.structured.get("probes", [])
                        live_targets = [p["url"] for p in probes if p.get("url")]

            # 3. Nuclei scan
            findings: list[dict[str, Any]] = []
            if live_targets:
                nuclei_result = await nuclei_scan(
                    {
                        "targets": live_targets,
                        "severity": severity,
                        "rate_limit": 150,
                        "timeout_sec": min(timeout_sec, 1800),
                    }
                )
                if not nuclei_result.is_error and nuclei_result.structured:
                    findings = nuclei_result.structured.get("findings", [])

            summary = {
                "targets": targets,
                "ports": ports,
                "hosts_discovered": len(hosts),
                "web_candidates": len(all_web_targets),
                "live_services": len(live_targets),
                "findings_count": len(findings),
                "findings": findings,
            }
            audit_event(
                self.log,
                "vuln_scan.done",
                hosts=len(hosts),
                live=len(live_targets),
                findings=len(findings),
            )
            return ToolResult(
                text=(
                    f"Full vuln scan — {len(hosts)} host(s), "
                    f"{len(live_targets)} live service(s), {len(findings)} finding(s)."
                ),
                structured=summary,
            )

        return ToolSpec(
            name="full_vuln_scan",
            description=(
                "Complete vulnerability scan workflow: Nmap port discovery, "
                "httpx liveness confirmation, then Nuclei vulnerability scan. "
                "All targets MUST be in scope."
            ),
            input_schema={
                "type": "object",
                "required": ["targets"],
                "properties": {
                    "targets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Hosts or IPs to scan.",
                    },
                    "ports": {
                        "type": "string",
                        "default": "1-1024",
                        "description": "Nmap port spec, e.g. '1-1024' or '80,443,8080'.",
                    },
                    "severity": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["critical", "high", "medium"],
                        "description": "Nuclei severity filter.",
                    },
                    "timing": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 5,
                        "default": 3,
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "minimum": 10,
                        "maximum": 3600,
                        "default": 600,
                    },
                },
                "additionalProperties": False,
            },
            handler=handler,
            dangerous=True,
            requires_scope_field="targets",
            tags=["workflow", "vuln-scan", "active"],
            when_to_use=[
                "User wants a comprehensive vulnerability assessment of in-scope hosts.",
                "After initial recon to validate findings with multiple scanners.",
            ],
            when_not_to_use=[
                "Target is out of scope.",
                "Only passive OSINT is authorized.",
            ],
            prerequisites=[
                "nmap, httpx, and nuclei binaries configured.",
                "Targets are inside authorized_scope.",
            ],
            pitfalls=[
                "Broad port ranges are slow; default 1-1024 is usually sufficient.",
                "Nuclei templates may produce false positives; triage findings before reporting.",
            ],
        )
