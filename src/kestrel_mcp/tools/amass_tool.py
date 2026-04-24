"""OWASP Amass attack-surface enumeration wrapper."""

from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any

from ..config import Settings
from ..domain import entities as ent
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class AmassModule(ToolModule):
    id = "amass"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = getattr(self.settings.tools, self.id, None)
        self._binary_hint = _block_get(block, "binary")
        self._output_dir = str(_block_get(block, "output_dir") or "~/.kestrel/runs/amass")

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "amass")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="amass_enum",
                description="Run OWASP Amass enum against an in-scope domain and persist discovered assets.",
                input_schema={
                    "type": "object",
                    "required": ["domain"],
                    "properties": {
                        "domain": {"type": "string"},
                        "mode": {"type": "string", "enum": ["passive", "active"], "default": "passive"},
                        "brute_force": {"type": "boolean", "default": False},
                        "wordlist": {"type": "string"},
                        "include_sources": {"type": "boolean", "default": True},
                        "include_ips": {"type": "boolean", "default": True},
                        "timeout_sec": {"type": "integer", "minimum": 30, "maximum": 7200, "default": 1800},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_enum,
                dangerous=True,
                requires_scope_field="domain",
                tags=["recon", "osint", "subdomains", "attack-surface"],
                phase="recon",
                complexity_tier=3,
                preferred_model_tier="standard",
                output_trust="untrusted",
                when_to_use=[
                    "User wants deeper attack-surface mapping than subfinder.",
                    "Need source/IP-enriched subdomain data for later httpx/nmap work.",
                ],
                when_not_to_use=[
                    "User asked for a quick lightweight passive pass; use subfinder first.",
                    "Target is not a domain or is outside authorized scope.",
                ],
                prerequisites=["Amass binary is installed.", "Domain is inside authorized_scope."],
                follow_ups=["Run httpx_probe on discovered names.", "Run nmap_scan on discovered IPs."],
                pitfalls=["active mode and brute_force are much noisier than passive mode."],
            ),
            ToolSpec(
                name="amass_version",
                description="Return the installed Amass version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_enum(self, arguments: dict[str, Any]) -> ToolResult:
        domain = str(arguments["domain"]).strip()
        await self.ensure_scope(domain, tool_name="amass_enum")

        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))

        output_dir = _expanded_dir(self._output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"amass_{_safe_name(domain)}.json"

        argv = [binary, "enum", "-d", domain, "-json", str(json_path)]
        if str(arguments.get("mode") or "passive") == "passive":
            argv.append("-passive")
        else:
            argv.append("-active")
        if bool(arguments.get("brute_force", False)):
            argv.append("-brute")
        if bool(arguments.get("include_sources", True)):
            argv.append("-src")
        if bool(arguments.get("include_ips", True)):
            argv.append("-ip")
        if wordlist := str(arguments.get("wordlist") or "").strip():
            argv += ["-w", wordlist]

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run Amass enum for {domain}.",
                structured={"dry_run": True, "argv": argv, "domain": domain, "output": str(json_path)},
            )

        result = await run_command(
            argv,
            timeout_sec=int(arguments.get("timeout_sec") or 1800),
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        raw_json = json_path.read_text(encoding="utf-8", errors="replace") if json_path.exists() else result.stdout
        records = _parse_amass_json(raw_json)
        names = sorted({r["name"] for r in records if r.get("name")})
        ips = sorted({ip for r in records for ip in r.get("addresses", [])})
        target_ids = await self._persist(domain, names, ips)

        audit_event(
            self.log,
            "amass.enum",
            domain=domain,
            names=len(names),
            ips=len(ips),
            exit_code=result.exit_code,
        )
        return ToolResult(
            text=f"Amass found {len(names)} name(s) and {len(ips)} IP address(es) for {domain}.",
            structured={
                "domain": domain,
                "records": records,
                "subdomains": names,
                "ips": ips,
                "count": len(names),
                "ip_count": len(ips),
                "output_file": str(json_path),
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
        return ToolResult(text=raw, structured={"raw": raw, "exit_code": result.exit_code}, is_error=not result.ok)

    async def _persist(self, domain: str, names: list[str], ips: list[str]) -> list[str]:
        target_ids: list[str] = []
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is None or not ctx.has_engagement():
                return target_ids
            engagement_id = ctx.require_engagement()
            apex = await ctx.target.add(
                engagement_id=engagement_id,
                kind=ent.TargetKind.DOMAIN,
                value=domain,
                discovered_by_tool="amass_enum",
            )
            target_ids.append(str(apex.id))
            for name in names:
                kind = ent.TargetKind.SUBDOMAIN if name != domain else ent.TargetKind.DOMAIN
                t = await ctx.target.add(
                    engagement_id=engagement_id,
                    kind=kind,
                    value=name,
                    parent_id=apex.id if name != domain else None,
                    discovered_by_tool="amass_enum",
                )
                target_ids.append(str(t.id))
            for value in ips:
                kind = ent.TargetKind.IPV6 if ":" in value else ent.TargetKind.IPV4
                t = await ctx.target.add(
                    engagement_id=engagement_id,
                    kind=kind,
                    value=value,
                    discovered_by_tool="amass_enum",
                )
                target_ids.append(str(t.id))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("amass.persist_failed", error=str(exc))
        return target_ids


def _parse_amass_json(text: str) -> list[dict[str, Any]]:  # noqa: C901
    if not text.strip():
        return []
    items: list[Any] = []
    try:
        parsed = json.loads(text)
        items = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    records: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("domain") or item.get("fqdn")
        addresses: list[str] = []
        for key in ("address", "ip"):
            if item.get(key):
                addresses.append(str(item[key]))
        raw_addresses = item.get("addresses") or []
        if isinstance(raw_addresses, list):
            for addr in raw_addresses:
                if isinstance(addr, dict) and addr.get("ip"):
                    addresses.append(str(addr["ip"]))
                elif isinstance(addr, str):
                    addresses.append(addr)
        valid_ips = []
        for addr in addresses:
            try:
                valid_ips.append(str(ipaddress.ip_address(addr.strip())))
            except ValueError:
                continue
        if name:
            records.append(
                {
                    "name": str(name).strip().lower(),
                    "addresses": sorted(set(valid_ips)),
                    "source": item.get("source") or item.get("sources"),
                }
            )
    return records


def _expanded_dir(raw: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    return path if path.is_absolute() else Path.cwd() / path


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "target"


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
