"""Recon workflow — multi-step reconnaissance orchestration.

This module exposes ONE MCP tool ``recon_target`` that chains:

    1. Shodan facet search across the target domain (``ssl.cert.subject.CN:target``)
       to discover assets by TLS certificate — the most reliable pivot.
    2. Resolve the discovered IPs for open ports / products / known vulns
       via ``shodan host``.
    3. Optionally kick a light Nuclei baseline scan (severity=high,critical
       only) against the discovered web-facing services.

The whole flow respects the scope guard — if ``target`` falls outside
``authorized_scope`` the workflow refuses to start.
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


class ReconWorkflow:
    """Build the ``recon_target`` tool spec."""

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        self.settings = settings
        self.scope_guard = scope_guard
        self.log = get_logger("workflow.recon")

    def spec(
        self,
        *,
        shodan_search: ToolHandler,
        shodan_host: ToolHandler,
        nuclei_scan: ToolHandler,
    ) -> ToolSpec:
        async def handler(arguments: dict[str, Any]) -> ToolResult:
            target = arguments["target"]
            await ensure_target_scope(
                self.scope_guard,
                self.settings,
                self.log,
                target,
                tool_name="recon_target",
            )
            do_vuln = bool(arguments.get("run_vuln_baseline", False))
            ip_limit = int(arguments.get("ip_limit", 20))

            shodan_query = f'ssl.cert.subject.CN:"{target}"'
            audit_event(self.log, "recon.start", target=target, do_vuln=do_vuln)

            search_result = await shodan_search({"query": shodan_query, "limit": ip_limit})
            if search_result.is_error:
                return search_result

            hits = (search_result.structured or {}).get("hits", [])
            ips = sorted({h["ip"] for h in hits if h.get("ip")})[:ip_limit]

            host_details: list[dict[str, Any]] = []
            for ip in ips:
                res = await shodan_host({"ip": ip})
                if not res.is_error and res.structured:
                    host_details.append(res.structured)

            vuln_findings: list[dict[str, Any]] = []
            if do_vuln and host_details:
                web_targets: list[str] = []
                for h in host_details:
                    ip = h.get("ip")
                    for port in h.get("ports", []):
                        if port in (80, 8080):
                            web_targets.append(f"http://{ip}:{port}")
                        elif port in (443, 8443):
                            web_targets.append(f"https://{ip}:{port}")
                web_targets = list(dict.fromkeys(web_targets))

                in_scope: list[str] = []
                for web_target in web_targets:
                    if await target_in_scope(
                        self.scope_guard,
                        self.settings,
                        self.log,
                        web_target,
                        tool_name="recon_target.nuclei_filter",
                    ):
                        in_scope.append(web_target)
                if in_scope:
                    nuclei_result = await nuclei_scan(
                        {
                            "targets": in_scope,
                            "severity": ["critical", "high"],
                            "rate_limit": 150,
                        }
                    )
                    if not nuclei_result.is_error and nuclei_result.structured:
                        vuln_findings = nuclei_result.structured.get("findings", [])

            summary = {
                "target": target,
                "shodan_query": shodan_query,
                "discovered_ips": ips,
                "host_count": len(host_details),
                "hosts": host_details,
                "vuln_findings_count": len(vuln_findings),
                "vuln_findings": vuln_findings,
            }
            audit_event(
                self.log,
                "recon.done",
                target=target,
                hosts=len(host_details),
                vulns=len(vuln_findings),
            )
            return ToolResult(
                text=(
                    f"Recon on '{target}' — {len(ips)} IP(s), {len(host_details)} host detail(s), "
                    f"{len(vuln_findings)} vuln finding(s)."
                ),
                structured=summary,
            )

        return ToolSpec(
            name="recon_target",
            description=(
                "Run a complete reconnaissance workflow on a target domain: Shodan "
                "certificate-based asset discovery, per-IP port & vuln enrichment, "
                "optional lightweight Nuclei baseline scan. Target MUST be in scope."
            ),
            input_schema={
                "type": "object",
                "required": ["target"],
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Root domain, e.g. 'example.com'.",
                    },
                    "ip_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 20,
                    },
                    "run_vuln_baseline": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, launch a critical+high Nuclei scan.",
                    },
                },
                "additionalProperties": False,
            },
            handler=handler,
            dangerous=True,
            requires_scope_field="target",
            tags=["workflow", "recon"],
        )
