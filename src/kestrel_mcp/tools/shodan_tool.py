"""Shodan tools.

Wraps the official ``shodan`` Python SDK so an LLM can do asset recon
without ever needing to run the shell CLI.

Exposed tools:
    * ``shodan_search``          — paginated search with facets
    * ``shodan_host``            — per-IP deep info
    * ``shodan_count``           — cheap query (0 credits)
    * ``shodan_facets``          — top-N breakdown
    * ``shodan_scan_submit``     — submit on-demand scan (uses scan credit)
    * ``shodan_account_info``   — check remaining credits
"""

from __future__ import annotations

import os
from typing import Any

from ..config import Settings
from ..core.context import current_context_or_none
from ..domain import entities as ent
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class ShodanModule(ToolModule):
    id = "shodan"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        self._api: Any | None = None

    def _require_api(self) -> Any:
        if self._api is not None:
            return self._api

        try:
            import shodan  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "Python package 'shodan' is not installed. Run: pip install shodan"
            ) from exc

        block = self.settings.tools.shodan
        api_key_env = getattr(block, "api_key_env", None) or "SHODAN_API_KEY"
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(
                f"Environment variable {api_key_env!r} is empty. Get a key at "
                "https://account.shodan.io/ and set it before starting the server."
            )

        self._api = shodan.Shodan(api_key)
        return self._api

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="shodan_count",
                description=(
                    "Count Shodan matches for a query. Consumes 0 credits. This is the "
                    "cheapest and safest way to test a query or size a population before "
                    "any paid search."
                ),
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "maxLength": 1024,
                            "description": (
                                "Shodan query. Space = AND. Examples: "
                                '"product:nginx country:US", "port:6379 -authentication", '
                                "'ssl.cert.subject.CN:\"acme.com\"'. "
                                'Country MUST be 2-letter ISO (US not "United States").'
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_count,
                tags=["recon", "osint", "free"],
                when_to_use=[
                    'User asks "how many X exist" / "how common is Y".',
                    "Before any shodan_search to verify the query has matches.",
                    "Comparing populations across countries / products.",
                    "Sanity-checking query syntax before burning credits.",
                ],
                when_not_to_use=[
                    "User wants actual IP records - use shodan_search.",
                    "Target is private (10.x, 192.168.x) - Shodan does not index RFC1918.",
                ],
                prerequisites=[
                    "SHODAN_API_KEY environment variable is set.",
                ],
                follow_ups=[
                    "If total > 0 and user wants records: call shodan_search with limit <= 100.",
                    "If total == 0: try dropping one filter (e.g. remove port:), or call "
                    "shodan_facets with facets=product:20 to see valid values.",
                    "If total > 10000: refine query with country / org filters; a broad "
                    "query will not fit in one search response anyway.",
                ],
                pitfalls=[
                    "Country code is 2-letter ISO. 'United States' will return 0.",
                    "Use space between filters, NOT comma. 'product:nginx,country:US' is wrong.",
                    "Shodan has no AND/OR keywords. Space already means AND.",
                    'Quotes needed only when value contains whitespace: org:"Amazon Inc".',
                    "Dash prefix means NEGATION: '-authentication' finds endpoints without auth.",
                ],
                example_conversation=(
                    'User: "how many Redis servers in China are unauthenticated?"\n'
                    'Agent -> shodan_count({"query": "product:redis -authentication country:CN"})\n'
                    'Result: {"total": 43218}\n'
                    'Agent: "Shodan sees 43,218 such Redis hosts. Pull samples?"'
                ),
                local_model_hints=(
                    "This is the SAFE default when the user uses words like 'count', "
                    "'how many', 'how common'. Do NOT default to shodan_search; always try "
                    "count first. If you are unsure whether the query is valid, call this - "
                    "it costs nothing."
                ),
            ),
            ToolSpec(
                name="shodan_search",
                description=(
                    "Return actual Shodan records (IP, port, banner preview, org). "
                    "Consumes 1 query credit per 100 results."
                ),
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "maxLength": 1024,
                            "description": "Same syntax as shodan_count.",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 1000,
                            "default": 50,
                            "description": "Max hits to return. Prefer <= 100 on first call.",
                        },
                        "page": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1,
                            "description": "Page number. Each page costs 1 extra credit.",
                        },
                        "facets": {
                            "type": "string",
                            "description": (
                                "Rare. Prefer shodan_facets instead. "
                                'If used, format "field:N,field:N".'
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_search,
                tags=["recon", "osint", "paid"],
                when_to_use=[
                    "User asks for 'list', 'show me', 'examples of' specific records.",
                    "shodan_count already returned > 0 and user explicitly agreed to pay.",
                    "Need concrete IPs/orgs to feed into downstream tools.",
                ],
                when_not_to_use=[
                    "shodan_count returned 0 - do NOT waste a credit.",
                    "Query is extremely broad (e.g. 'apache' alone, no filters).",
                    "User only asked for counts - use shodan_count.",
                    "Shodan plan is 'oss' (free) - search will return HTTP 403.",
                ],
                prerequisites=[
                    "SHODAN_API_KEY set.",
                    "Shodan plan supports search (check shodan_account_info first if unsure).",
                    "shodan_count returned non-zero for the same query.",
                ],
                follow_ups=[
                    "For each IP of interest: shodan_host to enrich with open ports and vulns.",
                    "If interested in distribution: shodan_facets (free).",
                    "If want to probe live web services: feed hit.ip into httpx/caido tools.",
                ],
                pitfalls=[
                    "HTTP 403 'Access denied' almost always means oss plan or expired key. "
                    "Call shodan_account_info to confirm.",
                    "limit=1000 is not faster; server paginates regardless.",
                    "Each hit's data_preview is truncated to 500 chars.",
                    "Do NOT parallelise multiple searches - sequential + narrow query.",
                ],
                example_conversation=(
                    'User: "find 5 older nginx in the US"\n'
                    'Agent -> shodan_count({"query": "product:nginx country:US version:1.14"})\n'
                    "Result: 12843 matches.\n"
                    'Agent -> shodan_search({"query": "product:nginx country:US version:1.14", "limit": 5})\n'
                    "Agent summarises the 5 hits with IP, org, port."
                ),
                local_model_hints=(
                    "ALWAYS call shodan_count first with the same query. If count is 0, "
                    "stop. If 403, call shodan_account_info. Never run search as the "
                    "very first action of a session."
                ),
            ),
            ToolSpec(
                name="shodan_host",
                description=(
                    "Deep information about a single IP: open ports, banners, detected "
                    "vulnerabilities, organization, geolocation."
                ),
                input_schema={
                    "type": "object",
                    "required": ["ip"],
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": (
                                "Public IPv4 or IPv6 only. "
                                "Private ranges (10/8, 192.168/16, 172.16/12) return empty."
                            ),
                        },
                        "history": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include banner history. Costs 1 additional credit.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_host,
                tags=["recon", "osint"],
                when_to_use=[
                    "User gives a specific public IP to investigate.",
                    "Enriching results from shodan_search before sending any packets.",
                    "Confirming what Shodan knows about a target you're about to test.",
                ],
                when_not_to_use=[
                    "IP is in private range - Shodan does not index it.",
                    "You only need a quick port check - too expensive for that.",
                ],
                prerequisites=[
                    "IP is publicly routable.",
                    "SHODAN_API_KEY set.",
                ],
                follow_ups=[
                    "If result lists CVEs: consider nuclei_scan with matching tags.",
                    "If ports 80/443 present: httpx_probe or caido_replay_request for HTTP details.",
                    "If os detected and vulnerable: searchsploit the os/version.",
                ],
                pitfalls=[
                    "Shodan data can be stale (re-scan cycles vary). Don't treat port list "
                    "as ground truth - verify with a live probe if planning exploitation.",
                    "vulns field is often empty even when vulns exist - absence != safety.",
                    "Calling with history=true costs 1 credit; default is free-ish.",
                ],
                example_conversation=(
                    'User: "look up 45.33.32.156"\n'
                    'Agent -> shodan_host({"ip": "45.33.32.156"})\n'
                    'Result: ports [22,80,9929], org "Linode", no known vulns.'
                ),
                local_model_hints=(
                    "Validate IP format before calling. If input looks like 'nmap.org' "
                    "(a hostname), this tool is WRONG - resolve it first or use a different "
                    "tool. Reject '127.0.0.1', '10.*', '192.168.*', '172.16-31.*' - these "
                    "are private and return nothing useful."
                ),
            ),
            ToolSpec(
                name="shodan_facets",
                description=(
                    "Top-N distribution of hits by a facet field "
                    "(country, port, product, org, vuln). Consumes 0 credits."
                ),
                input_schema={
                    "type": "object",
                    "required": ["query", "facets"],
                    "properties": {
                        "query": {"type": "string", "maxLength": 1024},
                        "facets": {
                            "type": "string",
                            "description": (
                                'Facet spec as a STRING, e.g. "country:10" or "port:20,country:10". '
                                "Note: this is the one place where comma-joined is correct."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_facets,
                tags=["recon", "analytics", "free"],
                when_to_use=[
                    "User asks 'where are X most common' / 'what ports does Y usually listen on'.",
                    "Before designing a targeted query, to understand the landscape.",
                    "Answering analytics questions without pulling records.",
                ],
                when_not_to_use=[
                    "Need per-IP data - use shodan_search.",
                    "Looking for a specific asset - use shodan_host.",
                ],
                follow_ups=[
                    "Use the top facet values to narrow a follow-on shodan_count or shodan_search.",
                ],
                pitfalls=[
                    "facets is a STRING here (e.g. 'country:10'), not an array. "
                    "One of the few places comma-separation is correct syntax.",
                    "Some facets (asn, os) require a paid plan - may error on oss.",
                    "Max 100 values per facet.",
                ],
                example_conversation=(
                    'User: "which countries run the most ElasticSearch?"\n'
                    'Agent -> shodan_facets({"query": "product:elasticsearch", "facets": "country:10"})'
                ),
                local_model_hints=(
                    "Field is a STRING not array. Write 'country:10' not ['country:10']. "
                    "N defaults high; you rarely need more than 10-20."
                ),
            ),
            ToolSpec(
                name="shodan_scan_submit",
                description=(
                    "Ask Shodan to actively scan an IP or CIDR. Consumes SCAN credits "
                    "(separate from query credits)."
                ),
                input_schema={
                    "type": "object",
                    "required": ["target"],
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": (
                                "Single IPv4, IPv6, or CIDR (e.g. 192.0.2.0/24). "
                                "MUST be in the authorized scope."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_scan_submit,
                dangerous=True,
                requires_scope_field="target",
                tags=["recon", "active", "paid"],
                when_to_use=[
                    "User explicitly asks to refresh Shodan data for a target.",
                    "Suspected that cached data is stale and user accepts the scan credit cost.",
                ],
                when_not_to_use=[
                    "You have not confirmed authorization for the target - REFUSE.",
                    "Just want cached info - use shodan_host (free-ish).",
                    "Plan is oss - no scan credits available.",
                ],
                prerequisites=[
                    "Target in authorized_scope (enforced).",
                    "Plan has scan_credits > 0 (check shodan_account_info).",
                    "Operator has explicitly confirmed this consumes a credit.",
                ],
                follow_ups=[
                    "Scan is async. After ~5-10 min, re-query with shodan_host to see fresh data.",
                ],
                pitfalls=[
                    "This is ACTIVE. Target may see packets from Shodan IPs.",
                    "Even a single IP costs 1 credit; a /24 is 256 credits.",
                    "OSS plan has 0 scan credits - call will fail.",
                ],
                local_model_hints=(
                    "NEVER auto-trigger this. Always pause and ask the user: "
                    "'Confirm: submit active Shodan scan on X? This consumes N credits.' "
                    "Only call after explicit yes."
                ),
            ),
            ToolSpec(
                name="shodan_account_info",
                description=(
                    "Return Shodan account plan and remaining query/scan credits. "
                    "Free, no side effects."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_account_info,
                tags=["meta", "free"],
                when_to_use=[
                    "Troubleshooting 403 errors from search / scan endpoints.",
                    "User asks about plan / credits / budget.",
                    "At the start of an engagement to confirm key works.",
                ],
                follow_ups=[
                    "If plan is 'oss': avoid shodan_search; use shodan_count and shodan_facets.",
                    "If query_credits low: switch to count-only mode or pause scanning.",
                ],
                pitfalls=[
                    "The field names are odd: 'plan' can be 'dev', 'oss', 'member', etc. "
                    "'oss' is the free tier and CANNOT search.",
                ],
                local_model_hints=(
                    "Call this FIRST when any shodan tool returns 403 or permission errors."
                ),
            ),
        ]

    async def _handle_search(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments["query"]
        limit = int(arguments.get("limit", 50))
        page = int(arguments.get("page", 1))
        facets = arguments.get("facets") or None

        api = self._require_api()
        try:
            raw = api.search(query, limit=limit, page=page, facets=facets)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Shodan search failed: {exc}")

        hits = [
            {
                "ip": m.get("ip_str"),
                "port": m.get("port"),
                "transport": m.get("transport"),
                "hostnames": m.get("hostnames", []),
                "org": m.get("org"),
                "country": (m.get("location") or {}).get("country_name"),
                "product": m.get("product"),
                "version": m.get("version"),
                "timestamp": m.get("timestamp"),
                "data_preview": (m.get("data") or "")[:500],
            }
            for m in raw.get("matches", [])
        ]

        # Persist discovered IPs as Targets in the active engagement, if any.
        ingested = await self._ingest_search_hits(hits)

        audit_event(
            self.log,
            "shodan.search",
            query=query,
            total=raw.get("total"),
            returned=len(hits),
            page=page,
            ingested_targets=ingested,
        )
        summary = f"Shodan returned {len(hits)} of {raw.get('total', 'unknown')} total hits."
        if ingested:
            summary += f" Saved {ingested} new target(s) to the active engagement."
        return ToolResult(
            text=summary,
            structured={
                "total": raw.get("total"),
                "facets": raw.get("facets"),
                "hits": hits,
                "ingested_targets": ingested,
            },
        )

    async def _handle_host(self, arguments: dict[str, Any]) -> ToolResult:
        ip = arguments["ip"]
        history = bool(arguments.get("history", False))

        api = self._require_api()
        try:
            info = api.host(ip, history=history)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Shodan host lookup failed: {exc}")

        summary = {
            "ip": info.get("ip_str"),
            "hostnames": info.get("hostnames", []),
            "org": info.get("org"),
            "isp": info.get("isp"),
            "asn": info.get("asn"),
            "country": info.get("country_name"),
            "city": info.get("city"),
            "os": info.get("os"),
            "ports": info.get("ports", []),
            "vulns": info.get("vulns", []),
            "tags": info.get("tags", []),
            "last_update": info.get("last_update"),
            "services_count": len(info.get("data", [])),
        }
        # Enrich the target record if one exists in the active engagement.
        enriched = await self._enrich_target_from_host(ip, summary)

        audit_event(
            self.log,
            "shodan.host",
            ip=ip,
            ports=summary["ports"],
            vulns=summary["vulns"],
            enriched=enriched,
        )
        msg = f"Host {ip}: {len(summary['ports'])} open ports, {len(summary['vulns'])} known vulns."
        if enriched:
            msg += " Target enrichment applied."
        return ToolResult(text=msg, structured={**summary, "enriched": enriched})

    async def _handle_count(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments["query"]
        api = self._require_api()
        try:
            raw = api.count(query)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Shodan count failed: {exc}")
        audit_event(self.log, "shodan.count", query=query, total=raw.get("total"))
        return ToolResult(
            text=f"{raw.get('total', 0)} hosts match '{query}'",
            structured={"total": raw.get("total", 0)},
        )

    async def _handle_facets(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments["query"]
        facets = arguments["facets"]
        api = self._require_api()
        try:
            raw = api.count(query, facets=facets)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Shodan facets failed: {exc}")
        audit_event(self.log, "shodan.facets", query=query, facets=facets)
        return ToolResult(
            text=f"Facet breakdown for '{query}'",
            structured={"total": raw.get("total", 0), "facets": raw.get("facets", {})},
        )

    async def _handle_scan_submit(self, arguments: dict[str, Any]) -> ToolResult:
        target = arguments["target"]
        self.scope_guard.ensure(target, tool_name="shodan_scan_submit")
        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would submit Shodan scan on {target}",
                structured={"dry_run": True, "target": target},
            )
        api = self._require_api()
        try:
            scan = api.scan(target)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Shodan scan submit failed: {exc}")
        audit_event(self.log, "shodan.scan_submit", target=target, scan_id=scan.get("id"))
        return ToolResult(
            text=f"Submitted scan {scan.get('id')} targeting {target}.",
            structured=scan,
        )

    async def _handle_account_info(self, _arguments: dict[str, Any]) -> ToolResult:
        api = self._require_api()
        try:
            info = api.info()
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Shodan account info failed: {exc}")
        return ToolResult(
            text=(
                f"plan={info.get('plan')} "
                f"query_credits={info.get('query_credits')} "
                f"scan_credits={info.get('scan_credits')}"
            ),
            structured=info,
        )

    # ------------------------------------------------------------------
    # Domain integration helpers (Sprint 3.2)
    # ------------------------------------------------------------------

    async def _ingest_search_hits(self, hits: list[dict[str, Any]]) -> int:
        """Save distinct IPs from a search as Target rows.

        Only runs when there's an active engagement AND the discovered
        target sits inside its scope (to avoid ingesting out-of-scope
        background noise the user didn't ask for).
        """

        ctx = current_context_or_none()
        if ctx is None or not ctx.has_engagement():
            return 0

        eid = ctx.engagement_id  # type: ignore[assignment]
        scope_snapshot = await ctx.scope.snapshot(eid)  # type: ignore[arg-type]
        if not scope_snapshot:
            return 0

        added = 0
        for hit in hits:
            ip = hit.get("ip")
            if not ip:
                continue
            try:
                ctx.scope.ensure_against(
                    scope_snapshot,
                    str(ip),
                    tool_name="shodan_search.ingest",
                    engagement_id=eid,  # type: ignore[arg-type]
                )
            except Exception:  # noqa: BLE001
                continue  # out of scope → skip silently
            await ctx.target.add(
                engagement_id=eid,  # type: ignore[arg-type]
                kind=ent.TargetKind.IPV4 if "." in ip and ":" not in ip else ent.TargetKind.IPV6,
                value=ip,
                discovered_by_tool="shodan_search",
            )
            added += 1
        return added

    async def _enrich_target_from_host(
        self,
        ip: str,
        host_summary: dict[str, Any],
    ) -> bool:
        """Merge-patch a Target with Shodan host details, if one exists in scope."""

        ctx = current_context_or_none()
        if ctx is None or not ctx.has_engagement():
            return False
        eid = ctx.engagement_id  # type: ignore[assignment]

        # Find existing target
        existing = await ctx.target.list_for_engagement(eid, kind=ent.TargetKind.IPV4)  # type: ignore[arg-type]
        match = next((t for t in existing if t.value == ip), None)
        if match is None:
            return False

        await ctx.target.update_enrichment(
            match.id,
            open_ports=list(host_summary.get("ports") or []),
            hostnames=list(host_summary.get("hostnames") or []),
            organization=host_summary.get("org"),
            country=host_summary.get("country"),
        )
        return True
