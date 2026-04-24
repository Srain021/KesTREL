"""Deep web application workflow.

Chains httpx -> katana -> nuclei -> sqlmap so the LLM can ask for one
high-level web pass without manually stitching every tool call.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..logging import audit_event, get_logger
from ..security import ScopeGuard
from ..tools.base import ToolHandler, ToolResult, ToolSpec, ensure_target_scope


class WebAppDeepScanWorkflow:
    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        self.settings = settings
        self.scope_guard = scope_guard
        self.log = get_logger("workflow.web_app_deep_scan")

    def spec(
        self,
        *,
        httpx_probe: ToolHandler,
        katana_crawl: ToolHandler,
        nuclei_scan: ToolHandler,
        sqlmap_scan: ToolHandler,
    ) -> ToolSpec:
        async def handler(arguments: dict[str, Any]) -> ToolResult:
            targets = [str(t).strip() for t in arguments["targets"] if str(t).strip()]
            for target in targets:
                await ensure_target_scope(
                    self.scope_guard,
                    self.settings,
                    self.log,
                    target,
                    tool_name="web_app_deep_scan",
                )

            timeout_sec = int(arguments.get("timeout_sec") or 1800)
            audit_event(self.log, "web_app_deep_scan.start", targets=len(targets))

            httpx_result = await httpx_probe(
                {
                    "targets": targets,
                    "tech_detect": True,
                    "status_code": True,
                    "title": True,
                    "timeout_sec": min(timeout_sec, 300),
                }
            )
            if httpx_result.is_error:
                return ToolResult(
                    text=f"web_app_deep_scan stopped at httpx_probe: {httpx_result.text}",
                    structured={"stage": "httpx_probe", "error": httpx_result.text},
                    is_error=True,
                )

            probes = (httpx_result.structured or {}).get("probes", [])
            live_urls = [p["url"] for p in probes if p.get("url")]
            if not live_urls:
                return ToolResult(
                    text="web_app_deep_scan found no live HTTP service.",
                    structured={"targets": targets, "live_urls": [], "findings": [], "sqlmap": []},
                )

            katana_result = await katana_crawl(
                {
                    "targets": live_urls,
                    "depth": int(arguments.get("depth") or 3),
                    "js_crawl": bool(arguments.get("js_crawl", True)),
                    "headless": bool(arguments.get("headless", False)),
                    "scope": str(arguments.get("scope") or "fqdn"),
                    "timeout_sec": min(timeout_sec, 900),
                }
            )
            crawled_urls = []
            if not katana_result.is_error and katana_result.structured:
                crawled_urls = [u["url"] for u in katana_result.structured.get("urls", []) if u.get("url")]

            nuclei_targets = list(dict.fromkeys(live_urls + crawled_urls))
            nuclei_result = await nuclei_scan(
                {
                    "targets": nuclei_targets,
                    "severity": arguments.get("severity", ["critical", "high", "medium"]),
                    "rate_limit": int(arguments.get("rate_limit") or 150),
                    "timeout_sec": min(timeout_sec, 1800),
                }
            )

            sqlmap_limit = int(arguments.get("sqlmap_limit") or 10)
            sqlmap_candidates = _sqlmap_candidates(crawled_urls or live_urls)[:sqlmap_limit]
            sqlmap_results: list[dict[str, Any]] = []
            for url in sqlmap_candidates:
                res = await sqlmap_scan(
                    {
                        "url": url,
                        "level": int(arguments.get("sqlmap_level") or 1),
                        "risk": int(arguments.get("sqlmap_risk") or 1),
                        "timeout_sec": min(timeout_sec, 1200),
                    }
                )
                sqlmap_results.append(
                    {
                        "url": url,
                        "is_error": res.is_error,
                        "summary": res.text,
                        "result": res.structured or {},
                    }
                )

            findings = []
            if nuclei_result.structured:
                findings.extend(nuclei_result.structured.get("findings", []))
            findings.extend(
                r["result"]
                for r in sqlmap_results
                if isinstance(r.get("result"), dict) and r["result"].get("injectable")
            )

            audit_event(
                self.log,
                "web_app_deep_scan.done",
                live=len(live_urls),
                crawled=len(crawled_urls),
                sqlmap=len(sqlmap_results),
                findings=len(findings),
            )
            return ToolResult(
                text=(
                    f"web_app_deep_scan: {len(live_urls)} live URL(s), "
                    f"{len(crawled_urls)} crawled URL(s), {len(sqlmap_results)} sqlmap check(s), "
                    f"{len(findings)} finding object(s)."
                ),
                structured={
                    "targets": targets,
                    "live_urls": live_urls,
                    "crawled_urls": crawled_urls,
                    "nuclei": nuclei_result.structured or {},
                    "sqlmap": sqlmap_results,
                    "findings": findings,
                },
                is_error=bool(nuclei_result.is_error and not findings),
            )

        return ToolSpec(
            name="web_app_deep_scan",
            description="Deep web workflow: httpx liveness, Katana crawling, Nuclei scan, then bounded sqlmap checks.",
            input_schema={
                "type": "object",
                "required": ["targets"],
                "properties": {
                    "targets": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "depth": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                    "js_crawl": {"type": "boolean", "default": True},
                    "headless": {"type": "boolean", "default": False},
                    "scope": {"type": "string", "enum": ["fqdn", "rdn", "dn"], "default": "fqdn"},
                    "severity": {"type": "array", "items": {"type": "string"}, "default": ["critical", "high", "medium"]},
                    "rate_limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 150},
                    "sqlmap_limit": {"type": "integer", "minimum": 0, "maximum": 50, "default": 10},
                    "sqlmap_level": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1},
                    "sqlmap_risk": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
                    "timeout_sec": {"type": "integer", "minimum": 30, "maximum": 7200, "default": 1800},
                },
                "additionalProperties": False,
            },
            handler=handler,
            dangerous=True,
            requires_scope_field="targets",
            tags=["workflow", "web", "scan", "active"],
            phase="workflow",
            complexity_tier=5,
            preferred_model_tier="strong",
            output_trust="sensitive",
            when_to_use=["User wants a full web app pass from liveness through crawl and SQLi checks."],
            prerequisites=["httpx, katana, nuclei, and sqlmap modules are enabled."],
            pitfalls=["sqlmap_dump_table is intentionally not called by this workflow."],
        )


def _sqlmap_candidates(urls: list[str]) -> list[str]:
    out: list[str] = []
    for url in urls:
        lower = url.lower()
        if "?" in url or any(marker in lower for marker in ("id=", "search", "query", "filter", "page=")):
            out.append(url)
    return list(dict.fromkeys(out))
