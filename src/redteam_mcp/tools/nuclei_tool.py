"""Nuclei tools.

Wraps the ``nuclei`` binary. Every invocation uses JSON output so results
are surfaced as structured MCP content.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import Settings
from ..core.context import current_context_or_none
from ..domain import entities as ent
from ..executor import resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


_SEVERITY_LEVELS = ["info", "low", "medium", "high", "critical"]


class NucleiModule(ToolModule):
    id = "nuclei"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.nuclei
        self._binary_hint: str | None = getattr(block, "binary", None)
        self._default_rate_limit: int = int(getattr(block, "default_rate_limit", 150))

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "nuclei")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="nuclei_scan",
                description=(
                    "Run Nuclei templated vulnerability scans against URLs. Produces "
                    "structured JSON findings with severity, CVE, CWE references."
                ),
                input_schema={
                    "type": "object",
                    "required": ["targets"],
                    "properties": {
                        "targets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "URLs, hostnames, or IPs to scan.",
                        },
                        "severity": {
                            "type": "array",
                            "items": {"type": "string", "enum": _SEVERITY_LEVELS},
                            "description": "Severity filter.",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Template tag filter, e.g. ['cve','rce'].",
                        },
                        "exclude_tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "templates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Explicit template paths/dirs to include.",
                        },
                        "rate_limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 1000,
                            "description": "Global requests per second cap.",
                        },
                        "concurrency": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Parallel templates to run.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 10,
                            "maximum": 3600,
                            "description": "Overall scan time budget.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_scan,
                dangerous=True,
                tags=["vuln-scan", "active"],
                when_to_use=[
                    "User asks to 'scan for vulns', 'check for CVEs', 'find weaknesses'.",
                    "Target is web-facing (has HTTP/HTTPS).",
                    "After httpx_probe or manual verification that target is alive.",
                    "Confirming a suspected known CVE (use tags=['cve','<cve-id>']).",
                ],
                when_not_to_use=[
                    "Target has only SSH / SMB / non-HTTP services - Nuclei focuses on HTTP.",
                    "User asked for specific exploit (sqlmap, metasploit) - use that tool.",
                    "Scope guard refused - do not try workarounds.",
                    "Target is unreachable (wait or remove).",
                ],
                prerequisites=[
                    "Nuclei binary resolvable (check via doctor or nuclei_version).",
                    "Template library exists. If first use, call nuclei_update_templates.",
                    "All targets are inside authorized_scope.",
                ],
                follow_ups=[
                    "critical finding: STOP and show user immediately; never continue automatically.",
                    "high findings: summarise top 3-5, ask if user wants a deeper severity=medium pass.",
                    "zero findings at critical+high: consider severity=['medium'] or more tags.",
                    "findings with CVE: optionally call nuclei_list_templates to find related tests.",
                ],
                pitfalls=[
                    "Never run with no severity filter on first call - produces 500+ findings.",
                    "rate_limit too high triggers WAFs and causes false negatives.",
                    "Default 300s timeout may not finish full scans - check timed_out field.",
                    "Partial results returned on timeout - inspect output.",
                    "target 'example.com' works, 'https://example.com' is clearer.",
                ],
                example_conversation=(
                    'User: "quick scan http://10.10.11.42"\n'
                    'Agent -> nuclei_scan({\n'
                    '    "targets": ["http://10.10.11.42"],\n'
                    '    "severity": ["critical", "high"]\n'
                    '})\n'
                    'Result: 3 findings (1 critical RCE, 2 high).\n'
                    'Agent summarises each with template_id, CVE, remediation.'
                ),
                local_model_hints=(
                    "ALWAYS pass severity=['critical','high'] on first scan. "
                    "NEVER call with no filters - you will get drowned in info-level results. "
                    "targets field is ARRAY of strings, not comma string. "
                    "If Nuclei binary missing, tell user to run 'redteam-mcp doctor'."
                ),
            ),
            ToolSpec(
                name="nuclei_update_templates",
                description=(
                    "Pull latest community templates from ProjectDiscovery. "
                    "Takes 30-60 seconds. Network required."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_update_templates,
                tags=["maintenance"],
                when_to_use=[
                    "First use of Nuclei in a new engagement.",
                    "Templates older than 7 days (weekly cadence recommended).",
                    "User asks 'why didn't Nuclei find CVE-X?' and the CVE is recent.",
                ],
                when_not_to_use=[
                    "Just updated. Don't call repeatedly in one session.",
                    "Air-gapped environment - will fail, no retry.",
                    "Low disk space - templates take ~100MB.",
                ],
                prerequisites=[
                    "Outbound HTTPS connectivity to github.com.",
                    "Nuclei binary installed.",
                ],
                follow_ups=[
                    "Proceed with planned nuclei_scan.",
                ],
                pitfalls=[
                    "Silent failure possible if network unstable. Check exit_code.",
                    "On Windows path with spaces may mis-parse - log tail helps debug.",
                ],
                local_model_hints=(
                    "Call ONCE per engagement, not per scan. Not idempotent across sessions."
                ),
            ),
            ToolSpec(
                name="nuclei_list_templates",
                description=(
                    "List installed templates matching tags / severity. Read-only, fast (<1s). "
                    "Useful for previewing what a scan will do before committing."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by template tags, e.g. ['cve2024','rce'].",
                        },
                        "severity": {
                            "type": "array",
                            "items": {"type": "string", "enum": _SEVERITY_LEVELS},
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_list_templates,
                tags=["meta", "free"],
                when_to_use=[
                    "User asks 'does Nuclei have templates for X?'.",
                    "Before a costly scan, to confirm relevant templates exist.",
                    "Exploring what CVE families are covered.",
                ],
                follow_ups=[
                    "count > 0: proceed to nuclei_scan with same filters.",
                    "count == 0: broaden tags / severity, or check nuclei_update_templates.",
                ],
                pitfalls=[
                    "Output is truncated to 500 paths in structured response.",
                    "Tag typos return 0 - try common tags: 'cve', 'rce', 'sqli', 'xss', 'misconfig'.",
                ],
                local_model_hints=(
                    "Free & fast. Prefer calling this BEFORE a scan to verify coverage."
                ),
            ),
            ToolSpec(
                name="nuclei_version",
                description="Installed Nuclei version. Use for troubleshooting only.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
                when_to_use=[
                    "Troubleshooting a failed scan (is binary even installed?).",
                    "User asks 'what version of Nuclei are we running?'.",
                ],
                local_model_hints=(
                    "Default first step when any nuclei tool errors unexpectedly."
                ),
            ),
            ToolSpec(
                name="nuclei_validate_template",
                description=(
                    "Validate a Nuclei YAML template syntactically. No network; does not run. "
                    "Use to check a custom template before shipping it."
                ),
                input_schema={
                    "type": "object",
                    "required": ["template_yaml"],
                    "properties": {
                        "template_yaml": {
                            "type": "string",
                            "description": "Raw YAML content (not a path, the text itself).",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_validate_template,
                tags=["meta"],
                when_to_use=[
                    "User pasted a Nuclei template and wants syntax check.",
                    "After writing or editing a custom template.",
                ],
                when_not_to_use=[
                    "Template is on disk at a path - just point nuclei_scan at it via templates arg.",
                ],
                pitfalls=[
                    "Expects RAW YAML string, not a file path. If user gave a path, read it first.",
                    "Validation checks syntax only; it does NOT verify the detection logic works.",
                ],
                local_model_hints=(
                    "template_yaml is the FULL YAML text. If user says 'validate ~/my.yaml', "
                    "read the file first and pass its contents, not the path."
                ),
            ),
        ]

    async def _handle_scan(self, arguments: dict[str, Any]) -> ToolResult:
        targets: list[str] = arguments["targets"]
        for t in targets:
            self.scope_guard.ensure(t, tool_name="nuclei_scan")

        binary = self._binary()
        argv: list[str] = [binary, "-jsonl", "-silent", "-disable-update-check"]

        if severity := arguments.get("severity"):
            argv += ["-severity", ",".join(severity)]
        if tags := arguments.get("tags"):
            argv += ["-tags", ",".join(tags)]
        if exclude := arguments.get("exclude_tags"):
            argv += ["-etags", ",".join(exclude)]
        for tpl in arguments.get("templates", []):
            argv += ["-t", tpl]

        rate = int(arguments.get("rate_limit") or self._default_rate_limit)
        argv += ["-rl", str(rate)]
        if concurrency := arguments.get("concurrency"):
            argv += ["-c", str(int(concurrency))]

        timeout = int(arguments.get("timeout_sec") or self.settings.execution.timeout_sec)

        stdin_blob = "\n".join(targets).encode("utf-8")

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv, "targets": targets},
            )

        result = await run_command(
            argv,
            timeout_sec=timeout,
            max_output_bytes=self.settings.execution.max_output_bytes,
            stdin_data=stdin_blob,
        )

        findings = self._parse_jsonl(result.stdout)
        by_sev: dict[str, int] = {}
        for f in findings:
            sev = (f.get("info") or {}).get("severity", "unknown")
            by_sev[sev] = by_sev.get(sev, 0) + 1

        # Persist findings into the engagement DB when context has one.
        persisted = await self._persist_findings(targets, findings)

        audit_event(
            self.log,
            "nuclei.scan",
            targets=targets,
            findings=len(findings),
            persisted=persisted,
            exit_code=result.exit_code,
            duration_sec=result.duration_sec,
            by_severity=by_sev,
        )

        summary_lines = [f"Nuclei finished in {result.duration_sec:.1f}s — {len(findings)} finding(s)."]
        if by_sev:
            summary_lines.append("Severity breakdown: " + ", ".join(
                f"{k}={v}" for k, v in sorted(by_sev.items())
            ))
        if persisted:
            summary_lines.append(f"Persisted {persisted} finding(s) into active engagement.")

        return ToolResult(
            text="\n".join(summary_lines),
            structured={
                "exit_code": result.exit_code,
                "duration_sec": result.duration_sec,
                "targets": targets,
                "findings_count": len(findings),
                "persisted_findings": persisted,
                "by_severity": by_sev,
                "findings": findings,
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
            },
        )

    async def _handle_update_templates(self, _arguments: dict[str, Any]) -> ToolResult:
        binary = self._binary()
        result = await run_command(
            [binary, "-update-templates", "-silent"],
            timeout_sec=self.settings.execution.timeout_sec,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        audit_event(self.log, "nuclei.update_templates", exit_code=result.exit_code)
        return ToolResult(
            text=("Templates updated." if result.ok else "Template update finished with errors."),
            structured={
                "exit_code": result.exit_code,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-2000:],
            },
            is_error=not result.ok,
        )

    async def _handle_list_templates(self, arguments: dict[str, Any]) -> ToolResult:
        binary = self._binary()
        argv = [binary, "-tl", "-silent"]
        if tags := arguments.get("tags"):
            argv += ["-tags", ",".join(tags)]
        if severity := arguments.get("severity"):
            argv += ["-severity", ",".join(severity)]

        result = await run_command(
            argv,
            timeout_sec=self.settings.execution.timeout_sec,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        templates = [line for line in result.stdout.splitlines() if line.strip()]
        return ToolResult(
            text=f"{len(templates)} template(s) match filter.",
            structured={
                "count": len(templates),
                "templates": templates[:500],
                "truncated_preview": len(templates) > 500,
            },
            is_error=not result.ok and not templates,
        )

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        binary = self._binary()
        result = await run_command(
            [binary, "-version"],
            timeout_sec=30,
            max_output_bytes=64 * 1024,
        )
        return ToolResult(
            text=(result.stderr or result.stdout).strip(),
            structured={"raw": result.stderr or result.stdout, "exit_code": result.exit_code},
            is_error=not result.ok,
        )

    async def _handle_validate_template(self, arguments: dict[str, Any]) -> ToolResult:
        import tempfile
        from pathlib import Path

        binary = self._binary()
        content = arguments["template_yaml"]
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            result = await run_command(
                [binary, "-validate", "-t", str(tmp_path), "-silent"],
                timeout_sec=30,
                max_output_bytes=64 * 1024,
            )
            return ToolResult(
                text=("Template is valid." if result.ok else "Template has errors."),
                structured={
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                is_error=not result.ok,
            )
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    @staticmethod
    def _parse_jsonl(text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # ------------------------------------------------------------------
    # Domain integration (Sprint 3.2)
    # ------------------------------------------------------------------

    async def _persist_findings(
        self,
        targets: list[str],
        findings: list[dict[str, Any]],
    ) -> int:
        """Write Nuclei JSONL findings into the engagement DB.

        Returns the number of Finding entities created. Silently no-ops when
        there is no active engagement bound — this lets the tool work in
        ad-hoc mode without a domain DB.
        """

        ctx = current_context_or_none()
        if ctx is None or not ctx.has_engagement():
            return 0
        eid = ctx.engagement_id  # type: ignore[assignment]

        # Build one Target per distinct target URL so findings can link to it.
        # De-dup via TargetService.add() which is idempotent.
        target_entities: dict[str, ent.Target] = {}
        for t_val in targets:
            tgt = await ctx.target.add(
                engagement_id=eid,  # type: ignore[arg-type]
                kind=ent.TargetKind.URL,
                value=t_val,
                discovered_by_tool="nuclei_scan",
            )
            target_entities[t_val] = tgt

        # Translate Nuclei JSONL entries to domain Findings.
        finding_entities: list[ent.Finding] = []
        for raw in findings:
            info = raw.get("info") or {}
            matched = raw.get("matched-at") or raw.get("host") or ""
            tgt = _best_target_for(matched, targets, target_entities)
            if tgt is None:
                continue
            severity = _nuclei_severity_to_domain(info.get("severity"))
            classification = info.get("classification") or {}

            f = ent.Finding(
                engagement_id=eid,  # type: ignore[arg-type]
                target_id=tgt.id,
                title=info.get("name") or raw.get("template-id") or "Nuclei finding",
                severity=severity,
                category=ent.FindingCategory.OTHER,
                discovered_by_tool="nuclei_scan",
                cwe=list(_as_list(classification.get("cwe-id"))),
                cve=list(_as_list(classification.get("cve-id"))),
                description=info.get("description", "")[:4000],
                remediation=info.get("remediation", "")[:4000],
                references=list(_as_list(info.get("reference"))),
                cvss_score=_coerce_cvss(classification.get("cvss-score")),
                cvss_vector=classification.get("cvss-metrics"),
            )
            finding_entities.append(f)

        if finding_entities:
            await ctx.finding.bulk_create(finding_entities)
        return len(finding_entities)


# ---------------------------------------------------------------------------
# Translation helpers (module-scope, reusable by tests)
# ---------------------------------------------------------------------------


_SEVERITY_MAP = {
    "info": ent.FindingSeverity.INFO,
    "low": ent.FindingSeverity.LOW,
    "medium": ent.FindingSeverity.MEDIUM,
    "high": ent.FindingSeverity.HIGH,
    "critical": ent.FindingSeverity.CRITICAL,
}


def _nuclei_severity_to_domain(value: Any) -> ent.FindingSeverity:
    if isinstance(value, str):
        return _SEVERITY_MAP.get(value.lower(), ent.FindingSeverity.INFO)
    return ent.FindingSeverity.INFO


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _coerce_cvss(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(10.0, v))


def _best_target_for(
    matched: str,
    targets: list[str],
    entities: dict[str, "ent.Target"],
) -> "ent.Target | None":
    """Pick the Target entity whose URL is a prefix of ``matched-at``."""

    if not entities:
        return None
    # direct match first
    if matched in entities:
        return entities[matched]
    # host-prefix match
    for t in sorted(targets, key=len, reverse=True):
        if matched.startswith(t):
            return entities[t]
    # fallback: first registered
    return next(iter(entities.values()))
