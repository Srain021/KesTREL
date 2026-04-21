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
            self._exec_spec(
                "impacket_psexec", "psexec",
                "Run Impacket psexec for an interactive SMB shell (temporary service).",
                transport_hint="SMB (445) service",
                when_to_use=[
                    "Confirmed local-admin creds on a Windows host and need an interactive shell.",
                    "SYSTEM-level exec is required (service-based exec grants SYSTEM).",
                    "Other Impacket transports (wmiexec) are blocked by GPO/firewall.",
                ],
                when_not_to_use=[
                    "Stealth-critical engagement — psexec creates a Windows service "
                    "(event IDs 7045, 4697 + friends).",
                    "Single command suffices — use impacket_smbexec to avoid the service.",
                    "No SMB/445 reachable — try impacket_wmiexec over 135/WMI.",
                    "Modern AV/EDR in place — the RemComSvc-*.exe service binary is trivially flagged.",
                ],
                follow_ups=[
                    "Verify the temporary service was uninstalled (sc query).",
                    "Review artifact log for the uploaded service binary path.",
                    "If admin confirmed, consider impacket_secretsdump on the same host.",
                ],
                pitfalls_extra=[
                    "psexec drops a service binary named RemComSvc-*.exe — a trivial fingerprint.",
                    "Event 7045 (service install) + 4697 (service created) + 4624/4672 (admin logon).",
                ],
                local_hint=(
                    "Use impacket_psexec only when you need a real shell. "
                    "For one-off commands, prefer smbexec (simpler) or wmiexec (stealthier). "
                    "The target arg is a hostname or IP, not a URL."
                ),
                example=(
                    'User: "get a shell on 10.10.11.42 as administrator"\n'
                    "Agent -> impacket_psexec({\n"
                    '    "target": "10.10.11.42",\n'
                    '    "username": "administrator",\n'
                    '    "password": "<cred>",\n'
                    '    "command": "whoami /all"\n'
                    "})\n"
                    "Inspect stdout for SYSTEM confirmation, then plan recon."
                ),
            ),
            self._exec_spec(
                "impacket_smbexec", "smbexec",
                "Run Impacket smbexec for single-command exec via temporary SMB service.",
                transport_hint="SMB (445) service (per-command)",
                when_to_use=[
                    "Single-command exec on a Windows host with admin creds; no shell needed.",
                    "psexec unavailable but SMB/445 is open.",
                    "Want a lower service-install footprint than psexec.",
                ],
                when_not_to_use=[
                    "Need an interactive shell — use impacket_psexec.",
                    "Command produces > 8 KB output — the named pipe handling is fragile.",
                    "Stealth ops — smbexec still creates a service PER invocation.",
                    "WMI (wmiexec) is available and preferred for lower noise.",
                ],
                follow_ups=[
                    "If multiple commands are planned, switch to psexec (interactive) to batch them.",
                    "Confirm service cleanup via a second smbexec call running sc query.",
                ],
                pitfalls_extra=[
                    "Each command creates & destroys a service — event spam proportional to call count.",
                    "Large output may be truncated by Impacket's named-pipe read.",
                ],
                local_hint=(
                    "smbexec is per-command. 10 calls = 10 service events. "
                    "Prefer wmiexec for stealth, psexec for interactivity, smbexec only when both are off the table."
                ),
            ),
            self._exec_spec(
                "impacket_wmiexec", "wmiexec",
                "Run Impacket wmiexec over DCOM/WMI. Stealthier than SMB transports (no service).",
                transport_hint="WMI/DCOM (135 + ephemeral)",
                when_to_use=[
                    "Admin creds + WMI reachable (135/DCOM); stealth preferred over SMB.",
                    "Target has Defender/EDR flagging psexec/smbexec service-creation patterns.",
                    "Quick recon output (whoami, ipconfig, tasklist) with minimal artifacts.",
                ],
                when_not_to_use=[
                    "WMI service disabled or DCOM blocked — fall back to smbexec.",
                    "Need file upload/download — semi-interactive WMI shell has no transfer primitive.",
                    "Target is non-Windows — WMI requires Windows Management Instrumentation.",
                ],
                follow_ups=[
                    "Log the WMI class touched (Win32_Process) — useful for detection mapping.",
                    "If wmiexec works but psexec doesn't, flag as EDR-gap finding for the report.",
                ],
                pitfalls_extra=[
                    "Semi-interactive: output routed via a temp file; occasionally flaky on slow links.",
                    "Requires WMI service running; many hardened environments disable it.",
                ],
                local_hint=(
                    "Prefer wmiexec for stealth ops — no service-install events. "
                    "Often works against hardened DCs where SMB transports are blocked."
                ),
            ),
            ToolSpec(
                name="impacket_secretsdump",
                description=(
                    "Extract SAM / NTDS / LSA secrets via DCSync, NTDS remote, or SAM hive. "
                    "High-value, HIGH-noise."
                ),
                input_schema=_credential_schema(include_command=False),
                handler=self._script_handler("secretsdump"),
                dangerous=True,
                requires_scope_field="target",
                tags=["ad", "credentials", "active", "post-ex"],
                when_to_use=[
                    "Confirmed Domain Admin (or user with DCSync replication rights).",
                    "Post-compromise of a domain controller — dump NTDS.dit contents.",
                    "Need NTLM hashes for pass-the-hash or Kerberos TGT crafting.",
                ],
                when_not_to_use=[
                    "Only have low-priv creds — will fail with 'Access denied' + noisy event 4662.",
                    "Not a domain engagement (local only) — use impacket_psexec for SAM hive locally instead.",
                    "Goal was code execution (use psexec/smbexec/wmiexec).",
                    "Target unreachable on 445 (DRSUAPI/RPC needs SMB).",
                ],
                prerequisites=[
                    "Impacket Python package (`pip show impacket`).",
                    "Credentials with sufficient privileges (DA / Enterprise Admin / replication rights).",
                    "Target is a DC or has SAM/SYSTEM hives readable over SMB.",
                    "Acknowledgement that output contains secrets — handle per engagement rules.",
                ],
                follow_ups=[
                    "Treat every returned line as SENSITIVE — route via CredentialService "
                    "(once a follow-up RFC enables it). Never commit raw dumps to artifacts.",
                    "Cracked hash? Use it downstream via psexec (-hashes) or NetExec (future RFC).",
                    "Look for krbtgt hash — enables Golden Ticket attacks; document but don't forge unless authorized.",
                    "Check service accounts for weak passwords (hashcat -m 1000).",
                ],
                pitfalls=[
                    "Plaintext credentials passed as argv — future RFC will route via CredentialService.",
                    "Large domains: NTDS dump takes minutes; bump timeout_sec >= 1800.",
                    "Event 4662 (directory object access) per dumped object. Domain Admins WILL see this.",
                    "Output includes krbtgt hash — leaking it compromises the whole domain.",
                    "Kerberos pre-auth data occasionally mis-parsed on older DCs; capture stderr_tail for debug.",
                ],
                local_model_hints=(
                    "HIGHEST-sensitivity Impacket tool. Output is ALWAYS secret material. "
                    "Do NOT echo stdout to chat unless the user explicitly asks; prefer a structured summary "
                    "(count of users dumped, krbtgt present Y/N). "
                    "Target MUST be a domain controller for DCSync."
                ),
                example_conversation=(
                    'User: "I got DA on the DC 10.10.11.5. Dump hashes."\n'
                    "Agent -> impacket_secretsdump({\n"
                    '    "target": "10.10.11.5",\n'
                    '    "username": "Administrator",\n'
                    '    "password": "<DA-password>",\n'
                    '    "domain": "htb.local",\n'
                    '    "timeout_sec": 1800\n'
                    "})\n"
                    "Summarize: N accounts dumped, krbtgt hash captured; mark as sensitive artifact."
                ),
            ),
            ToolSpec(
                name="impacket_get_user_spns",
                description=(
                    "Kerberoast: request TGS-REP for accounts with SPNs and capture blobs "
                    "for offline cracking."
                ),
                input_schema=_credential_schema(include_command=False),
                handler=self._script_handler("GetUserSPNs", spn_mode=True),
                dangerous=True,
                requires_scope_field="target",
                tags=["ad", "kerberoast", "active", "post-ex"],
                when_to_use=[
                    "Valid domain credentials (any user, admin NOT required).",
                    "Want to find service accounts potentially vulnerable to Kerberoasting.",
                    "Mapping AD attack surface after initial foothold.",
                ],
                when_not_to_use=[
                    "Target environment is WORKGROUP (no Kerberos).",
                    "DC unreachable on LDAP (389/636) — required for SPN enumeration.",
                    "Only have NT hashes (no cleartext) — GetUserSPNs wants cleartext password; "
                    "pass-the-hash support is not exposed yet.",
                ],
                prerequisites=[
                    "Impacket Python package installed.",
                    "Any valid domain user credentials (privilege level irrelevant).",
                    "LDAP (389) and Kerberos (88) reachable on the DC.",
                ],
                follow_ups=[
                    "Crack returned TGS-REP hashes offline with hashcat mode 13100.",
                    "High-value SPNs (MSSQLSvc, SQLServerAgent, HTTP) -> prioritize for cracking.",
                    "Cracked service-account password -> likely reusable across domain.",
                    "Empty result with user-count > 0 is suspicious — LDAP query may be filtered.",
                ],
                pitfalls=[
                    "Module name is case-sensitive: `GetUserSPNs` (not getuserspns).",
                    "`-request` flag is auto-added (spn_mode=True); without it, tool only LISTS SPNs.",
                    "Zero returns can mean: (a) no kerberoastable accounts, (b) LDAP bind failed, "
                    "or (c) AES-only preauth enforced.",
                    "Event 4769 (TGS request) fires per user targeted — stealth-visible.",
                    "Output is piped to stdout as hashcat-ready strings.",
                ],
                local_model_hints=(
                    "Kerberoast is 'cheap recon' — almost always worth trying post-foothold. "
                    "Cracking happens OFFLINE (hashcat -m 13100), so this tool is relatively quiet. "
                    "Target arg is the DC IP/hostname. No 'command' arg — this tool has no exec phase."
                ),
                example_conversation=(
                    'User: "look for kerberoastable service accounts."\n'
                    "Agent -> impacket_get_user_spns({\n"
                    '    "target": "10.10.11.5",\n'
                    '    "username": "lowpriv",\n'
                    '    "password": "<pw>",\n'
                    '    "domain": "htb.local"\n'
                    "})\n"
                    "Result: 3 SPNs; one MSSQLSvc/sqlprd01.htb.local:1433. "
                    "Flag the hash for offline hashcat (mode 13100)."
                ),
            ),
        ]

    def _exec_spec(
        self,
        name: str,
        script: str,
        description: str,
        *,
        transport_hint: str,
        when_to_use: list[str],
        when_not_to_use: list[str],
        follow_ups: list[str],
        pitfalls_extra: list[str] | None = None,
        local_hint: str,
        example: str | None = None,
    ) -> ToolSpec:
        base_pitfalls = [
            "Plaintext password passed as argv — route via CredentialService "
            "once a follow-up RFC wires it.",
            "Commands producing > 8 KB output may be truncated by Impacket's "
            "named-pipe buffer.",
            f"Transport: {transport_hint}. Failure usually means the transport "
            "is blocked by firewall / GPO / EDR.",
        ]
        return ToolSpec(
            name=name,
            description=description,
            input_schema=_credential_schema(include_command=True),
            handler=self._script_handler(script),
            dangerous=True,
            requires_scope_field="target",
            tags=["ad", "lateral-movement", "active"],
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
            prerequisites=[
                "Impacket Python package installed (`pip show impacket`).",
                "Authorized local-admin or domain-admin credentials for the target.",
                f"Target reachable on {transport_hint} ports.",
            ],
            follow_ups=follow_ups,
            pitfalls=base_pitfalls + (pitfalls_extra or []),
            local_model_hints=local_hint,
            example_conversation=example,
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
        "target": {
            "type": "string",
            "description": (
                "Hostname or IP of the target. Plain host, no URL scheme. "
                "MUST be inside the engagement scope."
            ),
        },
        "username": {
            "type": "string",
            "description": (
                "Authorized user account name without the domain prefix. "
                "Set 'domain' separately."
            ),
        },
        "password": {
            "type": "string",
            "description": (
                "Plaintext password. Passed as argv to Impacket today; will be "
                "routed through CredentialService once a future RFC wires it."
            ),
        },
        "domain": {
            "type": "string",
            "default": "",
            "description": (
                "Windows domain (FQDN like 'htb.local' or NetBIOS like 'HTB'). "
                "Empty string for local (non-domain) accounts."
            ),
        },
        "timeout_sec": {
            "type": "integer",
            "minimum": 10,
            "maximum": 3600,
            "description": (
                "Maximum runtime in seconds. Default 300 suits exec; "
                "secretsdump on a large domain may need >= 1800."
            ),
        },
    }
    required = ["target", "username", "password"]
    if include_command:
        props["command"] = {
            "type": "string",
            "default": "",
            "description": (
                "Shell command to execute (exec tools only). "
                "Quote carefully for cmd.exe; empty string for interactive shell."
            ),
        }
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
