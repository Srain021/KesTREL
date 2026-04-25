"""sqlmap non-interactive SQL injection wrapper."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..config import Settings
from ..core.redact import redact
from ..domain import entities as ent
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class SqlmapModule(ToolModule):
    id = "sqlmap"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = getattr(self.settings.tools, self.id, None)
        self._binary_hint = _block_get(block, "binary")
        self._output_dir = str(_block_get(block, "output_dir") or "~/.kestrel/runs/sqlmap")

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "sqlmap")

    def specs(self) -> list[ToolSpec]:
        base_props = _base_schema_props()
        return [
            ToolSpec(
                name="sqlmap_scan",
                description="Run sqlmap in non-interactive detection mode against an in-scope URL.",
                input_schema={
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        **base_props,
                        "parameter": {"type": "string"},
                        "level": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1},
                        "risk": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
                        "techniques": {"type": "string", "default": "BEUSTQ"},
                        "dbms": {"type": "string"},
                        "threads": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 30,
                            "maximum": 7200,
                            "default": 1800,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_scan,
                dangerous=True,
                requires_scope_field="url",
                tags=["web", "sqli", "active"],
                phase="web",
                complexity_tier=4,
                preferred_model_tier="strong",
                output_trust="sensitive",
                when_to_use=["A URL or request parameter may be SQL injectable."],
                when_not_to_use=[
                    "Target is not in scope.",
                    "User wants database dumping; use sqlmap_dump_table with acknowledgement.",
                ],
                prerequisites=["sqlmap binary installed.", "Target URL is alive and in scope."],
                follow_ups=["Create a fire-control packet before any dump or takeover action."],
                pitfalls=["Never expose cookies or dumped data in chat output."],
            ),
            ToolSpec(
                name="sqlmap_dump_table",
                description="Dump a specific database table with sqlmap after explicit operator acknowledgement.",
                input_schema={
                    "type": "object",
                    "required": ["url", "database", "table", "acknowledge_risk"],
                    "properties": {
                        **base_props,
                        "database": {"type": "string"},
                        "table": {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "start": {"type": "integer", "minimum": 1},
                        "stop": {"type": "integer", "minimum": 1},
                        "acknowledge_risk": {"type": "boolean"},
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 30,
                            "maximum": 14400,
                            "default": 3600,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_dump,
                dangerous=True,
                requires_scope_field="url",
                tags=["web", "sqli", "dump", "sensitive"],
                phase="post_exploit",
                complexity_tier=5,
                preferred_model_tier="strong",
                output_trust="sensitive",
                prerequisites=["Confirmed SQL injection.", "Explicit acknowledge_risk=true."],
                pitfalls=[
                    "Do not return dumped rows to the MCP client; only return counts and artifact path."
                ],
            ),
            ToolSpec(
                name="sqlmap_version",
                description="Return the installed sqlmap version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_scan(self, arguments: dict[str, Any]) -> ToolResult:
        url = str(arguments["url"]).strip()
        await self.ensure_scope(url, tool_name="sqlmap_scan")
        argv_or_error = self._base_argv(arguments)
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        argv = argv_or_error
        if parameter := str(arguments.get("parameter") or "").strip():
            argv += ["-p", parameter]
        argv += [
            "--level",
            str(int(arguments.get("level") or 1)),
            "--risk",
            str(int(arguments.get("risk") or 1)),
            "--technique",
            str(arguments.get("techniques") or "BEUSTQ"),
            "--threads",
            str(int(arguments.get("threads") or 1)),
        ]
        if dbms := str(arguments.get("dbms") or "").strip():
            argv += ["--dbms", dbms]

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run sqlmap scan for {url}.",
                structured={"dry_run": True, "argv": _redact_argv(argv)},
            )

        result = await run_command(
            argv,
            timeout_sec=int(arguments.get("timeout_sec") or 1800),
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        parsed = _parse_sqlmap_stdout(result.stdout)
        target_ids, finding_ids = await self._persist_scan(url, parsed)
        audit_event(
            self.log,
            "sqlmap.scan",
            url=url,
            injectable=parsed["injectable"],
            exit_code=result.exit_code,
        )
        return ToolResult(
            text=f"sqlmap scan completed for {url}; injectable={parsed['injectable']}.",
            structured={
                **parsed,
                "url": url,
                "output_dir": self._output_path(),
                "exit_code": result.exit_code,
                "stdout_tail": redact(result.stdout[-4000:]),
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
                "targets_created": target_ids,
                "findings_created": finding_ids,
            },
            is_error=not result.ok,
        )

    async def _handle_dump(self, arguments: dict[str, Any]) -> ToolResult:
        url = str(arguments["url"]).strip()
        await self.ensure_scope(url, tool_name="sqlmap_dump_table")
        if not bool(arguments.get("acknowledge_risk", False)):
            return ToolResult.error("sqlmap_dump_table requires acknowledge_risk=true.")
        argv_or_error = self._base_argv(arguments)
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        argv = argv_or_error
        argv += ["--dump", "-D", str(arguments["database"]), "-T", str(arguments["table"])]
        columns = [str(c).strip() for c in arguments.get("columns", []) if str(c).strip()]
        if columns:
            argv += ["-C", ",".join(columns)]
        if arguments.get("start"):
            argv += ["--start", str(int(arguments["start"]))]
        if arguments.get("stop"):
            argv += ["--stop", str(int(arguments["stop"]))]

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run sqlmap dump for {url}.",
                structured={"dry_run": True, "argv": _redact_argv(argv)},
            )

        result = await run_command(
            argv,
            timeout_sec=int(arguments.get("timeout_sec") or 3600),
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        audit_event(self.log, "sqlmap.dump_table", url=url, exit_code=result.exit_code)
        return ToolResult(
            text=f"sqlmap dump_table exited with code {result.exit_code}; results are under the sqlmap output directory.",
            structured={
                "url": url,
                "database": str(arguments["database"]),
                "table": str(arguments["table"]),
                "output_dir": self._output_path(),
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
        result = await run_command(
            [binary, "--version"], timeout_sec=30, max_output_bytes=64 * 1024
        )
        raw = (result.stdout or result.stderr).strip()
        return ToolResult(
            text=raw, structured={"raw": raw, "exit_code": result.exit_code}, is_error=not result.ok
        )

    def _base_argv(self, arguments: dict[str, Any]) -> list[str] | ToolResult:
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        output_dir = Path(self._output_path())
        output_dir.mkdir(parents=True, exist_ok=True)
        argv = [binary, "--batch", "--output-dir", str(output_dir), "-u", str(arguments["url"])]
        method = str(arguments.get("method") or "").strip().upper()
        if method:
            argv += ["--method", method]
        if data := str(arguments.get("data") or "").strip():
            argv += ["--data", data]
        headers = arguments.get("headers") or {}
        if isinstance(headers, dict):
            for key, value in sorted(headers.items()):
                argv += ["-H", f"{key}: {value}"]
        if cookie := str(arguments.get("cookie") or "").strip():
            argv += ["--cookie", cookie]
        return argv

    def _output_path(self) -> str:
        path = Path(os.path.expandvars(os.path.expanduser(self._output_dir)))
        return str(path if path.is_absolute() else Path.cwd() / path)

    async def _persist_scan(self, url: str, parsed: dict[str, Any]) -> tuple[list[str], list[str]]:
        target_ids: list[str] = []
        finding_ids: list[str] = []
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is None or not ctx.has_engagement():
                return target_ids, finding_ids
            engagement_id = ctx.require_engagement()
            target = await ctx.target.add(
                engagement_id=engagement_id,
                kind=ent.TargetKind.URL,
                value=url,
                discovered_by_tool="sqlmap_scan",
            )
            target_ids.append(str(target.id))
            if parsed.get("injectable"):
                title = f"SQL injection suspected: {parsed.get('parameter') or url}"
                finding = await ctx.finding.create(
                    engagement_id=engagement_id,
                    target_id=target.id,
                    title=title,
                    severity=ent.FindingSeverity.HIGH,
                    discovered_by_tool="sqlmap_scan",
                    category=ent.FindingCategory.INJECTION,
                    confidence=ent.Confidence.LIKELY,
                    description=f"sqlmap reported injectable parameter/technique: {parsed}",
                    remediation="Use parameterized queries and validate ORM/query builder usage.",
                )
                finding_ids.append(str(finding.id))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("sqlmap.persist_failed", error=str(exc))
        return target_ids, finding_ids


def _base_schema_props() -> dict[str, Any]:
    return {
        "url": {"type": "string"},
        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
        "data": {"type": "string"},
        "headers": {"type": "object", "additionalProperties": {"type": "string"}},
        "cookie": {"type": "string"},
    }


def _parse_sqlmap_stdout(text: str) -> dict[str, Any]:
    lower = text.lower()
    injectable = "is vulnerable" in lower or "parameter:" in lower and "type:" in lower
    parameter_match = re.search(r"Parameter:\s*([^\n]+)", text, re.IGNORECASE)
    dbms_match = re.search(r"back-end DBMS:\s*([^\n]+)", text, re.IGNORECASE)
    techniques = sorted(set(re.findall(r"Type:\s*([^\n]+)", text, re.IGNORECASE)))
    return {
        "injectable": injectable,
        "parameter": parameter_match.group(1).strip() if parameter_match else None,
        "dbms": dbms_match.group(1).strip() if dbms_match else None,
        "techniques": techniques,
    }


def _redact_argv(argv: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    sensitive_flags = {"--cookie", "--data", "-H"}
    for idx, part in enumerate(argv):
        if skip_next:
            redacted.append("<REDACTED>")
            skip_next = False
            continue
        redacted.append(part)
        if part in sensitive_flags and idx + 1 < len(argv):
            skip_next = True
    return redacted


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
