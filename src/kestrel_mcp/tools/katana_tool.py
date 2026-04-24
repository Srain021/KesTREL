"""ProjectDiscovery Katana crawling wrapper."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from ..config import Settings
from ..domain import entities as ent
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class KatanaModule(ToolModule):
    id = "katana"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.katana
        self._binary_hint: str | None = getattr(block, "binary", None)

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "katana")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="katana_crawl",
                description="Crawl in-scope web URLs with Katana and return structured discovered endpoints.",
                input_schema={
                    "type": "object",
                    "required": ["targets"],
                    "properties": {
                        "targets": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "depth": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                        "js_crawl": {"type": "boolean", "default": True},
                        "headless": {"type": "boolean", "default": False},
                        "scope": {"type": "string", "enum": ["fqdn", "rdn", "dn"], "default": "fqdn"},
                        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 3600, "default": 600},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_crawl,
                dangerous=True,
                requires_scope_field="targets",
                tags=["web", "crawl", "active"],
                phase="web",
                complexity_tier=2,
                preferred_model_tier="standard",
                output_trust="untrusted",
                when_to_use=[
                    "Need URLs/endpoints before nuclei or sqlmap.",
                    "Target is a live HTTP service confirmed by httpx.",
                ],
                when_not_to_use=["Target is not a URL.", "Only passive recon is authorized."],
                prerequisites=["Katana binary installed.", "Every target is inside authorized_scope."],
                follow_ups=["Feed discovered URLs into sqlmap_scan or nuclei_scan."],
                pitfalls=["headless=true requires a usable browser environment and is slower."],
            ),
            ToolSpec(
                name="katana_version",
                description="Return the installed Katana version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_crawl(self, arguments: dict[str, Any]) -> ToolResult:
        targets = [str(t).strip() for t in arguments["targets"] if str(t).strip()]
        for target in targets:
            await self.ensure_scope(target, tool_name="katana_crawl")

        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))

        argv = [
            binary,
            "-jsonl",
            "-silent",
            "-no-color",
            "-d",
            str(int(arguments.get("depth") or 3)),
            "-crawl-scope",
            str(arguments.get("scope") or "fqdn"),
        ]
        if bool(arguments.get("js_crawl", True)):
            argv.append("-jc")
        if bool(arguments.get("headless", False)):
            argv.append("-headless")

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would crawl {len(targets)} target(s) with Katana.",
                structured={"dry_run": True, "argv": argv, "targets": targets},
            )

        result = await run_command(
            argv,
            timeout_sec=int(arguments.get("timeout_sec") or 600),
            max_output_bytes=self.settings.execution.max_output_bytes,
            stdin_data=("\n".join(targets) + "\n").encode("utf-8"),
        )
        records = _parse_katana_jsonl(result.stdout)
        target_ids, finding_ids = await self._persist(records)

        audit_event(
            self.log,
            "katana.crawl",
            targets=len(targets),
            urls=len(records),
            exit_code=result.exit_code,
        )
        return ToolResult(
            text=f"Katana discovered {len(records)} URL(s).",
            structured={
                "targets": targets,
                "urls": records,
                "count": len(records),
                "interesting_count": len([r for r in records if r.get("interesting")]),
                "exit_code": result.exit_code,
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
                "targets_created": target_ids,
                "findings_created": finding_ids,
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
        return ToolResult(text=raw, structured={"raw": raw, "exit_code": result.exit_code}, is_error=not result.ok)

    async def _persist(self, records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        target_ids: list[str] = []
        finding_ids: list[str] = []
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is None or not ctx.has_engagement():
                return target_ids, finding_ids
            engagement_id = ctx.require_engagement()
            for record in records:
                url = str(record.get("url") or "")
                if not url:
                    continue
                target = await ctx.target.add(
                    engagement_id=engagement_id,
                    kind=ent.TargetKind.URL,
                    value=url,
                    discovered_by_tool="katana_crawl",
                )
                target_ids.append(str(target.id))
                if record.get("interesting"):
                    finding = await ctx.finding.create(
                        engagement_id=engagement_id,
                        target_id=target.id,
                        title=f"Interesting crawled endpoint: {url}",
                        severity=ent.FindingSeverity.INFO,
                        discovered_by_tool="katana_crawl",
                        category=ent.FindingCategory.INFORMATION_DISCLOSURE,
                        description="Katana identified an endpoint worth manual review.",
                    )
                    finding_ids.append(str(finding.id))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("katana.persist_failed", error=str(exc))
        return target_ids, finding_ids


def _parse_katana_jsonl(text: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
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
        request = item.get("request") if isinstance(item.get("request"), dict) else {}
        response = item.get("response") if isinstance(item.get("response"), dict) else {}
        url = item.get("url") or item.get("endpoint") or request.get("endpoint") or request.get("url")
        if not url:
            continue
        url = str(url).strip()
        if url in seen:
            continue
        seen.add(url)
        parsed = urlparse(url)
        method = item.get("method") or request.get("method") or "GET"
        status_code = item.get("status_code") or item.get("status-code") or response.get("status_code")
        interesting = _is_interesting_url(url) or bool(item.get("form") or item.get("forms"))
        out.append(
            {
                "url": url,
                "method": str(method).upper(),
                "host": parsed.netloc,
                "path": parsed.path or "/",
                "source": item.get("source"),
                "status_code": status_code,
                "interesting": interesting,
            }
        )
    return out


def _is_interesting_url(url: str) -> bool:
    lower = url.lower()
    markers = ("/admin", "login", "signin", "api/", "/api", "graphql", "upload", "debug", "swagger")
    return any(marker in lower for marker in markers)
