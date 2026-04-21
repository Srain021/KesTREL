"""Wrappers for selected Impacket example modules."""

from __future__ import annotations

import sys
from typing import Any

from ..config import Settings
from ..executor import run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolHandler, ToolModule, ToolResult, ToolSpec


class ImpacketModule(ToolModule):
    id = "impacket"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)

    def enabled(self) -> bool:
        return bool(_block_get(getattr(self.settings.tools, self.id, None), "enabled"))

    def specs(self) -> list[ToolSpec]:
        return [
            self._exec_spec("impacket_psexec", "psexec", "Run Impacket psexec against a host."),
            self._exec_spec("impacket_smbexec", "smbexec", "Run Impacket smbexec against a host."),
            self._exec_spec("impacket_wmiexec", "wmiexec", "Run Impacket wmiexec against a host."),
            ToolSpec(
                name="impacket_secretsdump",
                description="Run Impacket secretsdump against an in-scope host.",
                input_schema=_credential_schema(include_command=False),
                handler=self._script_handler("secretsdump"),
                dangerous=True,
                requires_scope_field="target",
                tags=["ad", "credentials", "active"],
                prerequisites=["impacket Python package installed.", "Valid authorized credentials."],
                pitfalls=["Outputs secrets; handle as sensitive and avoid sharing raw logs."],
            ),
            ToolSpec(
                name="impacket_get_user_spns",
                description="Run Impacket GetUserSPNs for Kerberoast discovery.",
                input_schema=_credential_schema(include_command=False),
                handler=self._script_handler("GetUserSPNs", spn_mode=True),
                dangerous=True,
                requires_scope_field="target",
                tags=["ad", "kerberoast", "active"],
                prerequisites=["impacket Python package installed.", "Domain credentials."],
                pitfalls=["Module name is case-sensitive: GetUserSPNs."],
            ),
        ]

    def _exec_spec(self, name: str, script: str, description: str) -> ToolSpec:
        return ToolSpec(
            name=name,
            description=description,
            input_schema=_credential_schema(include_command=True),
            handler=self._script_handler(script),
            dangerous=True,
            requires_scope_field="target",
            tags=["ad", "lateral-movement", "active"],
            prerequisites=["impacket Python package installed.", "Valid authorized credentials."],
            pitfalls=["Plaintext password input is temporary until RFC-003 credential store lands."],
        )

    def _script_handler(self, script: str, *, spn_mode: bool = False) -> ToolHandler:
        async def handler(arguments: dict[str, Any]) -> ToolResult:
            return await self._handle_script(script, arguments, spn_mode=spn_mode)

        return handler

    async def _handle_script(
        self,
        script: str,
        arguments: dict[str, Any],
        *,
        spn_mode: bool = False,
    ) -> ToolResult:
        target = str(arguments["target"]).strip()
        self.scope_guard.ensure(target, tool_name=f"impacket_{script.lower()}")
        identity = _identity(arguments, include_target=not spn_mode)
        argv = [sys.executable, "-m", f"impacket.examples.{script}", identity]
        if spn_mode:
            argv += ["-dc-ip", target, "-request"]
        if command := str(arguments.get("command") or "").strip():
            argv.append(command)
        return await self._run_script(script, target, argv, int(arguments.get("timeout_sec") or 300))

    async def _run_script(
        self,
        script: str,
        target: str,
        argv: list[str],
        timeout_sec: int,
    ) -> ToolResult:
        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run Impacket {script} against {target}",
                structured={"script": script, "target": target, "dry_run": True},
            )
        result = await run_command(
            argv,
            timeout_sec=timeout_sec,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        audit_event(self.log, f"impacket.{script}", target=target, exit_code=result.exit_code)
        return ToolResult(
            text=f"Impacket {script} exited with code {result.exit_code}.",
            structured={
                "script": script,
                "target": target,
                "exit_code": result.exit_code,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-2000:],
                "truncated": result.truncated,
            },
            is_error=not result.ok,
        )


def _credential_schema(*, include_command: bool) -> dict[str, Any]:
    props: dict[str, Any] = {
        "target": {"type": "string"},
        "username": {"type": "string"},
        "password": {"type": "string"},
        "domain": {"type": "string", "default": ""},
        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 3600},
    }
    required = ["target", "username", "password"]
    if include_command:
        props["command"] = {"type": "string", "default": ""}
    return {"type": "object", "required": required, "properties": props, "additionalProperties": False}


def _identity(arguments: dict[str, Any], *, include_target: bool) -> str:
    domain = str(arguments.get("domain") or "").strip()
    username = str(arguments["username"]).strip()
    password = str(arguments["password"])
    principal = f"{domain}/{username}" if domain else username
    value = f"{principal}:{password}"
    if include_target:
        value += f"@{str(arguments['target']).strip()}"
    return value


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
