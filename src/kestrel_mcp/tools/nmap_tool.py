"""Nmap binary wrapper."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from ..config import Settings
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec


class NmapModule(ToolModule):
    id = "nmap"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = self.settings.tools.nmap
        self._binary_hint: str | None = getattr(block, "binary", None)

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "nmap")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="nmap_scan",
                description="Run an in-scope Nmap TCP scan and parse XML output.",
                input_schema={
                    "type": "object",
                    "required": ["targets"],
                    "properties": {
                        "targets": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "ports": {"type": "string", "default": "1-1024"},
                        "scripts": {"type": "array", "items": {"type": "string"}},
                        "timing": {"type": "integer", "minimum": 0, "maximum": 5, "default": 3},
                        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 3600},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_scan,
                dangerous=True,
                requires_scope_field="targets",
                tags=["recon", "ports", "active"],
                when_to_use=[
                    "User asks for open ports or service discovery.",
                    "Need TCP service inventory before choosing a specialist scanner.",
                ],
                when_not_to_use=[
                    "User wants passive-only OSINT.",
                    "Targets are web URLs and only HTTP liveness is needed; use httpx_probe.",
                ],
                prerequisites=[
                    "Nmap binary installed and configured.",
                    "Windows scan modes may require Npcap.",
                    "Every target is inside authorized_scope.",
                ],
                follow_ups=[
                    "Use httpx_probe for discovered HTTP services.",
                    "Use nuclei_scan on live web URLs after confirming ports.",
                ],
                pitfalls=[
                    "Do not run broad port ranges by default; start with 1-1024.",
                    "NSE scripts can be intrusive; keep scripts explicit.",
                ],
                local_model_hints="targets is an array; ports is a string like '22,80,443'.",
            ),
            ToolSpec(
                name="nmap_os_detect",
                description="Run Nmap OS detection against one in-scope target.",
                input_schema={
                    "type": "object",
                    "required": ["target"],
                    "properties": {
                        "target": {"type": "string"},
                        "timing": {"type": "integer", "minimum": 0, "maximum": 5, "default": 3},
                        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 3600},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_os_detect,
                dangerous=True,
                requires_scope_field="target",
                tags=["recon", "os-detect", "active"],
                prerequisites=["Nmap binary installed.", "Target is inside authorized_scope."],
                pitfalls=["OS detection is active and may require elevated privileges."],
            ),
            ToolSpec(
                name="nmap_version",
                description="Return the installed Nmap version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_scan(self, arguments: dict[str, Any]) -> ToolResult:
        targets = [str(t).strip() for t in arguments["targets"] if str(t).strip()]
        for target in targets:
            self.scope_guard.ensure(target, tool_name="nmap_scan")
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))

        # Use TCP connect scan and skip host discovery by default so Windows
        # and non-root smoke scans do not require raw packet capture privileges.
        argv = [binary, "-sT", "-Pn", "-oX", "-", "-p", str(arguments.get("ports") or "1-1024")]
        argv.append(f"-T{int(arguments.get('timing') or 3)}")
        if scripts := arguments.get("scripts"):
            argv += ["--script", ",".join(str(s) for s in scripts)]
        argv += targets
        return await self._run_nmap(argv, int(arguments.get("timeout_sec") or 300), "nmap.scan")

    async def _handle_os_detect(self, arguments: dict[str, Any]) -> ToolResult:
        target = str(arguments["target"]).strip()
        self.scope_guard.ensure(target, tool_name="nmap_os_detect")
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        argv = [binary, "-O", "-oX", "-", f"-T{int(arguments.get('timing') or 3)}", target]
        return await self._run_nmap(
            argv,
            int(arguments.get("timeout_sec") or 300),
            "nmap.os_detect",
        )

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        result = await run_command([binary, "--version"], timeout_sec=30, max_output_bytes=64 * 1024)
        raw = (result.stdout or result.stderr).strip()
        return ToolResult(
            text=raw.splitlines()[0] if raw else "",
            structured={"raw": raw, "exit_code": result.exit_code},
            is_error=not result.ok,
        )

    async def _run_nmap(self, argv: list[str], timeout_sec: int, event: str) -> ToolResult:
        if self.settings.security.dry_run:
            return ToolResult(text=f"[dry-run] would run: {' '.join(argv)}", structured={"argv": argv})
        result = await run_command(
            argv,
            timeout_sec=timeout_sec,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        parsed = parse_nmap_xml(result.stdout)
        audit_event(
            self.log,
            event,
            hosts=len(parsed["hosts"]),
            exit_code=result.exit_code,
            duration_sec=result.duration_sec,
        )
        return ToolResult(
            text=f"Nmap parsed {len(parsed['hosts'])} host(s).",
            structured={
                **parsed,
                "exit_code": result.exit_code,
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
            },
            is_error=not result.ok,
        )


def parse_nmap_xml(xml_text: str) -> dict[str, Any]:
    try:
        import nmap as python_nmap  # type: ignore[import-untyped]

        scanner = python_nmap.PortScanner()
        parsed = scanner.analyse_nmap_xml_scan(xml_text)
        return _normalise_python_nmap(parsed)
    except Exception:  # noqa: BLE001
        return _parse_nmap_xml_stdlib(xml_text)


def _normalise_python_nmap(parsed: dict[str, Any]) -> dict[str, Any]:
    hosts: list[dict[str, Any]] = []
    for address, host in (parsed.get("scan") or {}).items():
        ports: list[dict[str, Any]] = []
        for proto in ("tcp", "udp"):
            for port, pdata in (host.get(proto) or {}).items():
                ports.append(
                    {
                        "port": int(port),
                        "protocol": proto,
                        "state": pdata.get("state"),
                        "service": pdata.get("name"),
                        "product": pdata.get("product"),
                        "version": pdata.get("version"),
                    }
                )
        hosts.append(
            {
                "address": address,
                "status": (host.get("status") or {}).get("state"),
                "hostnames": [h.get("name") for h in host.get("hostnames", []) if h.get("name")],
                "ports": ports,
                "osmatches": host.get("osmatch") or [],
            }
        )
    return {"hosts": hosts}


def _parse_nmap_xml_stdlib(xml_text: str) -> dict[str, Any]:
    if not xml_text.strip():
        return {"hosts": []}
    root = ET.fromstring(xml_text)
    hosts: list[dict[str, Any]] = []
    for host in root.findall("host"):
        addr = host.find("address")
        status = host.find("status")
        hostnames = [h.get("name") for h in host.findall("./hostnames/hostname") if h.get("name")]
        ports = []
        for port in host.findall("./ports/port"):
            state = port.find("state")
            service = port.find("service")
            ports.append(
                {
                    "port": int(port.get("portid") or 0),
                    "protocol": port.get("protocol"),
                    "state": state.get("state") if state is not None else None,
                    "service": service.get("name") if service is not None else None,
                    "product": service.get("product") if service is not None else None,
                    "version": service.get("version") if service is not None else None,
                }
            )
        hosts.append(
            {
                "address": addr.get("addr") if addr is not None else None,
                "status": status.get("state") if status is not None else None,
                "hostnames": hostnames,
                "ports": ports,
                "osmatches": [
                    {"name": m.get("name"), "accuracy": m.get("accuracy")}
                    for m in host.findall("./os/osmatch")
                ],
            }
        )
    return {"hosts": hosts}
