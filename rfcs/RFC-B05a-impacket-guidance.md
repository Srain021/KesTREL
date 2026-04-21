---
id: RFC-B05a
title: Tool guidance completeness — Impacket module (highest-risk AD tools)
epic: B-CoreHardening
status: done
owner: coordinator
role: backend-engineer
blocking_on: [RFC-002]
edition: both
budget:
  max_files_touched: 5
  max_new_files: 1
  max_lines_added: 380
  max_minutes_human: 30
  max_tokens_model: 16000
files_to_read:
  - src/kestrel_mcp/tools/impacket_tool.py
  - src/kestrel_mcp/tools/nuclei_tool.py
  - src/kestrel_mcp/tools/base.py
files_will_touch:
  - rfcs/RFC-B05a-impacket-guidance.md            # new
  - src/kestrel_mcp/tools/impacket_tool.py        # modified
  - tests/unit/tools/test_impacket_tool.py        # modified
  - rfcs/INDEX.md                                 # modified
  - CHANGELOG.md                                  # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/tools/test_impacket_tool.py -v
rollback_cmd: |
  git checkout -- src/kestrel_mcp/tools/impacket_tool.py tests/unit/tools/test_impacket_tool.py rfcs/INDEX.md CHANGELOG.md
  if exist rfcs\RFC-B05a-impacket-guidance.md del rfcs\RFC-B05a-impacket-guidance.md
skill_id: rfc-b05a-impacket-guidance
---

# RFC-B05a — Tool guidance completeness for Impacket

## Mission

给 Impacket 5 个 AD 高危工具补齐 `when_to_use` / `when_not_to_use` /
`prerequisites` / `follow_ups` / `pitfalls` / `local_model_hints` /
`example_conversation` + 每个 param 加 `description`，并加一条 module 级
regression 测试。

## Context

- 2026-04-21 peer audit: 75 个 MCP tool 里 guidance 覆盖不均匀；高危工具
  (Impacket/Sliver/Havoc/Evilginx/Ligolo/Caido) 尤其薄。
- 本 RFC 是 B05 系列的第一阶段 (a)，用 Impacket 作范例。后续：
    - B05b: Sliver (8 tools)
    - B05c: Havoc + Evilginx (6 + 5 tools)
    - B05d: Ligolo + Caido (5 tools + sessions)
    - B05e: Engagement + Workflow tools
    - B05f: Epic G gaps (ffuf_param_fuzz / nmap_os_detect / bloodhound_*)
           + 跨 module param description sweep
- 模板参考：`nuclei_tool.py::nuclei_scan` (最完整的 ToolSpec)。
- Impacket 是本轮最高风险选择：5 个工具全 `dangerous=True`，包含
  `secretsdump` (dumps krbtgt) 和 Kerberoast。guidance 薄意味着 agent 可
  能误用（e.g. 对非 DC 目标跑 secretsdump，或对无 Kerberos 的 WORKGROUP
  跑 GetUserSPNs）。

## Non-goals

- **不改 handler 逻辑** — 纯 data / guidance 扩充；runtime behavior 零变化。
- **不改 `_credential_schema()` 的字段** —— 只补 `description`。
- **不引入 CredentialService 集成** —— `password` 字段说明里 flag 后续 RFC
  会做，但本 RFC 不碰。
- **不改其他 tool module** —— B05b-f 是独立后续 RFC。

## Design

三处 REPLACE，一处测试增补：

1. `_credential_schema()`：在每个 property 里加 `description`（6 个 params）
2. `_exec_spec()` helper：签名加 keyword-only 的 guidance 参数
   (`when_to_use`, `when_not_to_use`, `follow_ups`, `transport_hint`,
   `pitfalls_extra`, `local_hint`, `example`)，body 用它们填 ToolSpec
3. `specs()` 返回列表：3 个 `_exec_spec()` 调用各带专属 guidance；
   `impacket_secretsdump` 和 `impacket_get_user_spns` 的两个 ToolSpec
   内联全部 guidance 字段
4. 测试：加 `test_impacket_tools_have_complete_guidance()` — 遍历所有
   specs 断言 dangerous tool 必须有 non-empty `when_to_use` /
   `when_not_to_use` / `prerequisites` / `follow_ups` / `pitfalls` /
   `local_model_hints`，且所有 input_schema properties 有 `description`

此测试变成 regression guard：未来新加 Impacket 工具必须写 guidance
才能通过 pytest。

## Steps

### Step 1 — REPLACE `_credential_schema()` 加 param descriptions

```
REPLACE src/kestrel_mcp/tools/impacket_tool.py
<<<<<<< SEARCH
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
=======
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
>>>>>>> REPLACE
```

### Step 2 — REPLACE `_exec_spec()` helper to accept guidance kwargs

```
REPLACE src/kestrel_mcp/tools/impacket_tool.py
<<<<<<< SEARCH
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
=======
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
>>>>>>> REPLACE
```

### Step 3 — REPLACE `specs()` to pass guidance + expand secretsdump/SPNs ToolSpecs

```
REPLACE src/kestrel_mcp/tools/impacket_tool.py
<<<<<<< SEARCH
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
=======
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
>>>>>>> REPLACE
```

### Step 4 — APPEND guidance-completeness regression test

```
APPEND tests/unit/tools/test_impacket_tool.py


def test_impacket_tools_have_complete_guidance():
    """Every Impacket ToolSpec (all dangerous) must ship full guidance + param descriptions.

    This is a regression guard: adding a new Impacket tool without guidance
    will fail this test. Re-enable fields as coverage grows across B05b-f.
    """

    from kestrel_mcp.config import Settings
    from kestrel_mcp.security import ScopeGuard
    from kestrel_mcp.tools.impacket_tool import ImpacketModule

    module = ImpacketModule(Settings(), ScopeGuard([]))
    specs = module.specs()
    assert len(specs) == 5, "Impacket module ships exactly 5 tools today."

    required_nonempty = (
        "when_to_use",
        "when_not_to_use",
        "prerequisites",
        "follow_ups",
        "pitfalls",
    )
    for spec in specs:
        assert spec.dangerous, f"{spec.name}: all Impacket tools must stay dangerous=True."
        for field_name in required_nonempty:
            value = getattr(spec, field_name)
            assert value, (
                f"{spec.name}: guidance field '{field_name}' is empty. "
                "Every high-risk Impacket ToolSpec must populate it (see RFC-B05a)."
            )
        assert spec.local_model_hints, (
            f"{spec.name}: local_model_hints is None. "
            "Dangerous tools must carry an explicit weak-model hint (RFC-B05a)."
        )

        props = spec.input_schema.get("properties", {})
        assert props, f"{spec.name}: input_schema has no properties."
        for prop_name, prop_def in props.items():
            assert "description" in prop_def and prop_def["description"].strip(), (
                f"{spec.name}: property '{prop_name}' is missing a description "
                "(RFC-B05a requires every param to be self-documenting)."
            )
```

### Step 5 — INDEX row + CHANGELOG entry

```
REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-B01 | Propagate core_errors everywhere  | open   | RFC-002     |       |
=======
| RFC-B01 | Propagate core_errors everywhere  | open   | RFC-002     |       |
| RFC-B05a | Tool guidance — Impacket         | open   | RFC-002     | agent |
>>>>>>> REPLACE
```

```
APPEND CHANGELOG.md

### Tool guidance hardening — Impacket (RFC-B05a)
- `src/kestrel_mcp/tools/impacket_tool.py`:
  - `_credential_schema()` — every param now carries a `description`
    (closes the 28 missing-param-description gap peer flagged).
  - `_exec_spec()` helper accepts per-tool `when_to_use`,
    `when_not_to_use`, `follow_ups`, `transport_hint`, `pitfalls_extra`,
    `local_hint`, `example` kwargs.
  - `psexec`, `smbexec`, `wmiexec` — each ships distinct guidance covering
    transport, stealth tradeoffs, event-log footprint, and follow-up
    playbook.
  - `secretsdump`, `get_user_spns` — inline full guidance blocks including
    krbtgt-sensitivity warning, Kerberoast mode requirements, offline-crack
    follow-ups.
- `tests/unit/tools/test_impacket_tool.py`:
  - New `test_impacket_tools_have_complete_guidance` acts as a regression
    guard; any future Impacket spec without full guidance fails pytest.
- First phase of the B05 series (tool guidance completeness). Follow-ups:
  B05b (Sliver), B05c (Havoc+Evilginx), B05d (Ligolo+Caido), B05e
  (Engagement+Workflow), B05f (Epic G gaps + cross-module param sweep).
```

### Step 6 — verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_impacket_tool.py -v
```

### Step 7 — regression

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

Step 4 新测试：
- Impacket 5 个 ToolSpec 全部 `dangerous=True`
- 每个 spec 5 个 guidance list 非空 (`when_to_use`/`when_not_to_use`/
  `prerequisites`/`follow_ups`/`pitfalls`)
- 每个 spec `local_model_hints` 非 None
- 所有 `input_schema.properties` 每个都有非空 `description`

## Post-checks

- [ ] `git diff --stat` 只列 `files_will_touch` 里的 5 个文件
- [ ] `pytest tests/unit/tools/test_impacket_tool.py` 全绿，包含新
      regression 测试
- [ ] `full_verify.py` 仍 8/8（无 runtime 行为变化）
- [ ] `kestrel list-tools | findstr impacket` — Impacket 5 个工具仍列出
- [ ] Post-commit sanity: `git status --short | Measure-Object` → Count 0

## Rollback plan

见 front-matter `rollback_cmd`。纯字符串 / schema 变化，无 DB / 外部副作用。

## Updates to other docs

- `CHANGELOG.md` 见 Step 5
- `rfcs/INDEX.md` 新加一行 B05a
- 不改 TOOLS_MATRIX（工具身份未变）

## Notes for executor

- **纯 data change**：没碰 handler、runtime、schema 结构。如果 full_verify 挂了，
  大概率是 SEARCH 块没精准匹配（Impacket 原文件是 peer 在 RFC-G06 里写的，
  H01 rename 后 path 变 `src/kestrel_mcp/` 但函数签名没变 — 见 files_to_read 的
  impacket_tool.py 实地情况）。
- `_exec_spec()` 旧签名只有 3 个位置参数；新签名有 3 个位置 + 6 个
  keyword-only。`specs()` 的 3 个调用必须改成 keyword 调用才能传新参数 ——
  Step 3 一次改完。
- `local_model_hints` 是 `str | None`，不是 `list`。测试断言 truthy（非 None 非空）。
- 引号风格：代码里多行字符串用 Python 3 的显式 concat（`"line1 " "line2"`）或
  `(...)` 隐式 concat。保留原风格。
- `example_conversation` 换行符用 `\n`；引用 JSON 里的 `"` 靠 Python 字符串
  转义 `\"`。
- Impacket 5 个工具都是 `dangerous=True`，这个保证 regression 测试的
  `spec.dangerous` 断言始终成立。

## Changelog

- **2026-04-21 v1.0** — Initial spec authored by coordinator
  (spec-author role). Targets the highest-risk tool module (Impacket)
  first per peer audit priority.
