"""NetExec (nxc) wrappers for AD/SMB credential workflows."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from ..config import Settings
from ..domain import entities as ent
from ..domain.errors import DomainError
from ..executor import ToolNotFoundError, resolve_binary, run_command
from ..logging import audit_event
from ..security import ScopeGuard
from .base import ToolModule, ToolResult, ToolSpec

_NTLM_RE = re.compile(r"^[A-Fa-f0-9]{32}$")
_TGS_RE = re.compile(r"\$krb5tgs\$[^\s]+")


class NetExecModule(ToolModule):
    id = "netexec"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = getattr(self.settings.tools, self.id, None)
        self._binary_hint = _block_get(block, "binary")
        self._workspace = str(_block_get(block, "workspace") or "kestrel")

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "nxc")

    def specs(self) -> list[ToolSpec]:
        auth_props = _auth_props()
        return [
            ToolSpec(
                name="netexec_smb_auth",
                description="Validate SMB credentials against in-scope targets using NetExec.",
                input_schema={
                    "type": "object",
                    "required": ["targets", "username"],
                    "properties": {**auth_props, "targets": _targets_prop()},
                    "additionalProperties": False,
                },
                handler=self._handle_smb_auth,
                dangerous=True,
                requires_scope_field="targets",
                tags=["ad", "smb", "credentials", "active"],
                phase="ad",
                complexity_tier=4,
                preferred_model_tier="strong",
                output_trust="sensitive",
                when_to_use=["Need to validate authorized credentials over SMB."],
                prerequisites=["NetExec nxc binary installed.", "Targets are in scope."],
                pitfalls=["Exactly one of credential_ref, password, ntlm_hash must be supplied."],
            ),
            ToolSpec(
                name="netexec_smb_enum",
                description="Run selected SMB enumeration checks with NetExec.",
                input_schema={
                    "type": "object",
                    "required": ["targets", "username", "enum_flags"],
                    "properties": {
                        **auth_props,
                        "targets": _targets_prop(),
                        "enum_flags": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["shares", "users", "sessions", "policy", "local_groups"],
                            },
                            "minItems": 1,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_smb_enum,
                dangerous=True,
                requires_scope_field="targets",
                tags=["ad", "smb", "enum", "active"],
                phase="ad",
                output_trust="sensitive",
            ),
            ToolSpec(
                name="netexec_smb_exec",
                description="Execute a remote SMB command via NetExec after explicit acknowledgement.",
                input_schema={
                    "type": "object",
                    "required": ["targets", "username", "command", "acknowledge_risk"],
                    "properties": {
                        **auth_props,
                        "targets": _targets_prop(),
                        "command": {"type": "string"},
                        "exec_method": {"type": "string", "enum": ["wmiexec", "atexec", "smbexec"], "default": "wmiexec"},
                        "acknowledge_risk": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_smb_exec,
                dangerous=True,
                requires_scope_field="targets",
                tags=["ad", "smb", "exec", "active", "post-ex"],
                phase="post_exploit",
                complexity_tier=5,
                preferred_model_tier="strong",
                output_trust="sensitive",
                prerequisites=["Confirmed admin rights.", "acknowledge_risk=true."],
            ),
            ToolSpec(
                name="netexec_ldap_kerberoast",
                description="Request Kerberoastable TGS hashes with NetExec LDAP and seal them into CredentialService.",
                input_schema={
                    "type": "object",
                    "required": ["target", "username"],
                    "properties": {**auth_props, "target": {"type": "string"}},
                    "additionalProperties": False,
                },
                handler=self._handle_ldap_kerberoast,
                dangerous=True,
                requires_scope_field="target",
                tags=["ad", "ldap", "kerberoast", "credentials", "active"],
                phase="ad",
                output_trust="sensitive",
            ),
            ToolSpec(
                name="netexec_version",
                description="Return the installed NetExec version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta", "free"],
            ),
        ]

    async def _handle_smb_auth(self, arguments: dict[str, Any]) -> ToolResult:
        targets = _targets(arguments)
        for target in targets:
            await self.ensure_scope(target, tool_name="netexec_smb_auth")
        argv_or_error = await self._base_argv("smb", targets, arguments)
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        return await self._run(argv_or_error, "netexec.smb_auth", targets, arguments, parser="auth")

    async def _handle_smb_enum(self, arguments: dict[str, Any]) -> ToolResult:
        targets = _targets(arguments)
        for target in targets:
            await self.ensure_scope(target, tool_name="netexec_smb_enum")
        argv_or_error = await self._base_argv("smb", targets, arguments)
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        argv = argv_or_error
        for flag in arguments["enum_flags"]:
            argv.append(_enum_flag(str(flag)))
        return await self._run(argv, "netexec.smb_enum", targets, arguments, parser="enum")

    async def _handle_smb_exec(self, arguments: dict[str, Any]) -> ToolResult:
        if not bool(arguments.get("acknowledge_risk", False)):
            return ToolResult.error("netexec_smb_exec requires acknowledge_risk=true.")
        targets = _targets(arguments)
        for target in targets:
            await self.ensure_scope(target, tool_name="netexec_smb_exec")
        argv_or_error = await self._base_argv("smb", targets, arguments)
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        argv = argv_or_error + [
            "--exec-method",
            str(arguments.get("exec_method") or "wmiexec"),
            "-x",
            str(arguments["command"]),
        ]
        return await self._run(argv, "netexec.smb_exec", targets, arguments, parser="exec")

    async def _handle_ldap_kerberoast(self, arguments: dict[str, Any]) -> ToolResult:
        target = str(arguments["target"]).strip()
        await self.ensure_scope(target, tool_name="netexec_ldap_kerberoast")
        argv_or_error = await self._base_argv("ldap", [target], arguments)
        if isinstance(argv_or_error, ToolResult):
            return argv_or_error
        argv = argv_or_error + ["--kerberoasting", "-"]
        return await self._run(argv, "netexec.ldap_kerberoast", [target], arguments, parser="kerberoast")

    async def _handle_version(self, _arguments: dict[str, Any]) -> ToolResult:
        try:
            binary = self._binary()
        except ToolNotFoundError as exc:
            return ToolResult.error(str(exc))
        result = await run_command([binary, "--version"], timeout_sec=30, max_output_bytes=64 * 1024)
        raw = (result.stdout or result.stderr).strip()
        return ToolResult(text=raw, structured={"raw": raw, "exit_code": result.exit_code}, is_error=not result.ok)

    async def _base_argv(
        self,
        protocol: str,
        targets: list[str],
        arguments: dict[str, Any],
    ) -> list[str] | ToolResult:
        try:
            binary = self._binary()
            auth = await self._auth_args(arguments)
        except (ToolNotFoundError, DomainError, ValueError) as exc:
            return ToolResult.error(str(exc))
        argv = [binary, protocol, *targets, "--workspace", self._workspace]
        domain = str(arguments.get("domain") or "").strip()
        if domain:
            argv += ["-d", domain]
        if bool(arguments.get("local_auth", False)):
            argv.append("--local-auth")
        if bool(arguments.get("kerberos", False)):
            argv.append("-k")
        argv += ["-u", str(arguments["username"]), *auth]
        return argv

    async def _auth_args(self, arguments: dict[str, Any]) -> list[str]:
        supplied = [
            bool(arguments.get("credential_ref")),
            bool(arguments.get("password")),
            bool(arguments.get("ntlm_hash")),
        ]
        if sum(1 for present in supplied if present) != 1:
            raise ValueError("Provide exactly one of credential_ref, password, or ntlm_hash.")
        if arguments.get("credential_ref"):
            secret = await _unseal_credential(str(arguments["credential_ref"]))
            return ["-H", secret] if _looks_hash(secret) else ["-p", secret]
        if arguments.get("ntlm_hash"):
            return ["-H", str(arguments["ntlm_hash"])]
        return ["-p", str(arguments["password"])]

    async def _run(
        self,
        argv: list[str],
        event: str,
        targets: list[str],
        arguments: dict[str, Any],
        *,
        parser: str,
    ) -> ToolResult:
        safe_argv = _redact_argv(argv)
        if self.settings.security.dry_run:
            return ToolResult(text=f"[dry-run] would run {event}.", structured={"dry_run": True, "argv": safe_argv, "targets": targets})
        result = await run_command(
            argv,
            timeout_sec=int(arguments.get("timeout_sec") or 600),
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        raw_stdout = result.stdout
        auth_results = _parse_nxc_auth(raw_stdout) if parser in {"auth", "enum", "exec"} else []
        kerberoast_hashes = _parse_kerberoast_hashes(raw_stdout) if parser == "kerberoast" else []
        stdout = _redact_text(raw_stdout, arguments)
        target_ids = await self._persist_targets(targets, event.replace(".", "_"))
        credential_ids = await self._seal_kerberoast(kerberoast_hashes)
        kerberoast_details = [
            {
                "hash": value,
                "identity": _kerberoast_identity(value),
                "hashcat_mode": 13100,
                "credential_id": credential_ids[idx] if idx < len(credential_ids) else None,
            }
            for idx, value in enumerate(kerberoast_hashes)
        ]
        audit_event(self.log, event, targets=len(targets), exit_code=result.exit_code)
        return ToolResult(
            text=f"NetExec {event} exited with code {result.exit_code}.",
            structured={
                "event": event,
                "protocol": argv[1] if len(argv) > 1 else None,
                "targets": targets,
                "argv": safe_argv,
                "auth_source": _auth_source(arguments),
                "auth_results": auth_results,
                "parsed_line_count": len([line for line in raw_stdout.splitlines() if line.strip()]),
                "output_lines": [line for line in stdout.splitlines() if line.strip()],
                "kerberoast_count": len(kerberoast_hashes),
                "kerberoast_hashes": kerberoast_details,
                "exit_code": result.exit_code,
                "stdout": stdout,
                "stdout_tail": stdout[-4000:],
                "stderr_tail": _redact_text(result.stderr[-2000:], arguments),
                "truncated": result.truncated,
                "targets_created": target_ids,
                "credentials_created": credential_ids,
            },
            is_error=not result.ok,
        )

    async def _persist_targets(self, targets: list[str], tool_name: str) -> list[str]:
        ids: list[str] = []
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is None or not ctx.has_engagement():
                return ids
            engagement_id = ctx.require_engagement()
            for target in targets:
                kind = ent.TargetKind.HOSTNAME
                try:
                    ip = ipaddress.ip_address(target)
                    kind = ent.TargetKind.IPV6 if isinstance(ip, ipaddress.IPv6Address) else ent.TargetKind.IPV4
                except ValueError:
                    pass
                row = await ctx.target.add(
                    engagement_id=engagement_id,
                    kind=kind,
                    value=target,
                    discovered_by_tool=tool_name,
                )
                ids.append(str(row.id))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("netexec.persist_targets_failed", error=str(exc))
        return ids

    async def _seal_kerberoast(self, hashes: list[str]) -> list[str]:
        ids: list[str] = []
        if not hashes:
            return ids
        try:
            from ..core.context import current_context_or_none

            ctx = current_context_or_none()
            if ctx is None or not ctx.has_engagement():
                return ids
            engagement_id = ctx.require_engagement()
            for value in hashes:
                cred = await ctx.credential.seal(
                    engagement_id=engagement_id,
                    kind=ent.CredentialKind.KERBEROS_TGS,
                    identity=_kerberoast_identity(value),
                    plaintext=value,
                    obtained_from_tool="netexec_ldap_kerberoast",
                    secret_metadata={"hashcat_mode": "13100"},
                    tags=["kerberoast", "netexec"],
                )
                ids.append(str(cred.id))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("netexec.credential_persist_failed", error=str(exc))
        return ids


async def _unseal_credential(reference: str) -> str:
    from ..core.context import current_context_or_none

    ctx = current_context_or_none()
    if ctx is None or not ctx.has_engagement():
        raise DomainError("credential_ref requires an active engagement context.")
    return await ctx.credential.unseal(reference)


def _targets(arguments: dict[str, Any]) -> list[str]:
    return [str(t).strip() for t in arguments["targets"] if str(t).strip()]


def _targets_prop() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "minItems": 1}


def _auth_props() -> dict[str, Any]:
    return {
        "username": {"type": "string"},
        "credential_ref": {"type": "string"},
        "password": {"type": "string"},
        "ntlm_hash": {"type": "string"},
        "domain": {"type": "string"},
        "local_auth": {"type": "boolean", "default": False},
        "kerberos": {"type": "boolean", "default": False},
        "timeout_sec": {"type": "integer", "minimum": 30, "maximum": 7200, "default": 600},
    }


def _enum_flag(value: str) -> str:
    mapping = {
        "shares": "--shares",
        "users": "--users",
        "sessions": "--sessions",
        "policy": "--pass-pol",
        "local_groups": "--local-groups",
    }
    return mapping[value]


def _looks_hash(value: str) -> bool:
    return bool(_NTLM_RE.match(value.strip()) or ":" in value and all(_NTLM_RE.match(part) for part in value.split(":")[-2:]))


def _parse_nxc_auth(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if "[+]" not in line and "Pwn3d" not in line:
            continue
        host_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
        rows.append(
            {
                "target": host_match.group(0) if host_match else None,
                "success": "[+]" in line or "Pwn3d" in line,
                "admin": "Pwn3d" in line,
                "line": line[-500:],
            }
        )
    return rows


def _parse_kerberoast_hashes(text: str) -> list[str]:
    return sorted(set(match.group(0) for match in _TGS_RE.finditer(text)))


def _kerberoast_identity(value: str) -> str:
    match = re.search(r"\$krb5tgs\$\d+\$\*?([^$:\s]+)", value)
    return match.group(1) if match else value[:64]


def _redact_argv(argv: list[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for idx, part in enumerate(argv):
        if skip:
            out.append("<REDACTED>")
            skip = False
            continue
        out.append(part)
        if part in {"-p", "-H"} and idx + 1 < len(argv):
            skip = True
    return out


def _redact_text(text: str, arguments: dict[str, Any]) -> str:
    redacted = text
    for key in ("password", "ntlm_hash"):
        value = str(arguments.get(key) or "")
        if value:
            redacted = redacted.replace(value, "<REDACTED>")
    return redacted


def _auth_source(arguments: dict[str, Any]) -> str:
    if arguments.get("credential_ref"):
        return "credential_ref"
    if arguments.get("ntlm_hash"):
        return "ntlm_hash"
    if arguments.get("password"):
        return "password"
    return "none"


def _block_get(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)
    return getattr(block, key, None)
