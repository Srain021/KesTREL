---
id: RFC-B05b1
title: Tool guidance completeness — Sliver server lifecycle + raw command (4 of 8)
epic: B-CoreHardening
status: done
owner: coordinator
role: backend-engineer
blocking_on: [RFC-002]
edition: both
budget:
  max_files_touched: 5
  max_new_files: 2
  max_lines_added: 400
  max_minutes_human: 30
  max_tokens_model: 18000
files_to_read:
  - src/kestrel_mcp/tools/sliver_tool.py
  - src/kestrel_mcp/tools/nuclei_tool.py
  - src/kestrel_mcp/tools/impacket_tool.py
files_will_touch:
  - rfcs/RFC-B05b1-sliver-server-guidance.md       # new
  - src/kestrel_mcp/tools/sliver_tool.py           # modified
  - tests/unit/tools/test_sliver_tool.py           # new (first sliver test file)
  - rfcs/INDEX.md                                  # modified
  - CHANGELOG.md                                   # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/tools/test_sliver_tool.py -v
rollback_cmd: |
  git checkout -- src/kestrel_mcp/tools/sliver_tool.py rfcs/INDEX.md CHANGELOG.md
  if exist tests\unit\tools\test_sliver_tool.py del tests\unit\tools\test_sliver_tool.py
  if exist rfcs\RFC-B05b1-sliver-server-guidance.md del rfcs\RFC-B05b1-sliver-server-guidance.md
skill_id: rfc-b05b1-sliver-server-guidance
---

# RFC-B05b1 — Sliver server lifecycle + run_command guidance

## Mission

给 Sliver 4 个 server/operator 级 tools 补齐完整 guidance，并建立 sliver_tool
的第一个测试文件（含 regression guard）。

## Context

- 2026-04-21 peer audit: Sliver 8 tools 几乎只有短 `description` + schema；
  无 `when_to_use` / `when_not_to_use` / `follow_ups` / `local_model_hints`.
- B05b 拆为 **b1 (server lifecycle)** + **b2 (ops: sessions/jobs/implant/exec)**，
  budget 各自在 cap 内。本 RFC 是 b1。
- Sliver 是目前支持的最敏感 C2 框架 —— implant 生成、session 内命令执行是 post-ex
  核心动作，guidance 薄意味着 local 模型可能在错的时机启 server / 随手跑错命令。
- 发现 sliver_tool.py 没有 test 文件。本 RFC 同时创建 `test_sliver_tool.py` 作为
  regression guard + 起点（后续 B05b2 和日常开发都可以往里加）。

## Non-goals

- 不改 handler 逻辑、不改 subprocess 调用、不改 argv 构造。纯 guidance + schema
  description 补齐。
- 不做 b2 范围的 4 个 tool (list_sessions/list_listeners/generate_implant/
  execute_in_session) —— 留给 RFC-B05b2。
- 不加 handler-level 测试（scope 拒绝/干跑/error path 等功能测试）—— 那是独立
  work，本 RFC 只补 `test_sliver_tools_have_complete_guidance` 的 regression
  guard.
- 不碰其他 tool module。

## Design

4 个 REPLACE（每个 ToolSpec 一个）+ 1 个 WRITE (new test file).

每个 tool 补齐：
- `when_to_use` (3-4 bullets)
- `when_not_to_use` (2-4 bullets, 视 tool 危险程度)
- `prerequisites` (2-3 bullets)
- `follow_ups` (2-3 bullets)
- `pitfalls` (3-4 bullets)
- `local_model_hints` (1 句 weak-model 友好提示)
- `example_conversation` (仅 dangerous 工具)

补全规则：
- `sliver_start_server` (dangerous=True): **全部字段**，含 example
- `sliver_stop_server` (non-dangerous): when_to_use/when_not_to_use/pitfalls/local_hint
- `sliver_server_status` (non-dangerous, meta/free): when_to_use/follow_ups/pitfalls/local_hint (跳过 when_not_to_use 因为 status check 总是安全的)
- `sliver_run_command` (dangerous=True, power-user escape): **全部字段**，含 example

Regression test 对应：
- dangerous tools must have ALL guidance fields non-empty
- non-dangerous tools must have when_to_use + local_model_hints (core minimum)
- 所有 schema properties must have `description`

## Steps

### Step 1 — REPLACE sliver_start_server ToolSpec

```
REPLACE src/kestrel_mcp/tools/sliver_tool.py
<<<<<<< SEARCH
            ToolSpec(
                name="sliver_start_server",
                description=(
                    "Start sliver-server in the background. It will run unattended and "
                    "persist its state in ~/.sliver/. First-time startup initialises "
                    "certificates and can take ~30s."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "daemon": {
                            "type": "boolean",
                            "default": True,
                            "description": "Run as daemon (vs attached TTY).",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start_server,
                dangerous=True,
                tags=["c2"],
            ),
=======
            ToolSpec(
                name="sliver_start_server",
                description=(
                    "Start sliver-server in the background. Persistent state lives in "
                    "~/.sliver/. First-time startup initialises certificates and can take ~30s."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "daemon": {
                            "type": "boolean",
                            "default": True,
                            "description": "Run detached from the invoking TTY (default). "
                                           "Set false only for interactive debugging.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_start_server,
                dangerous=True,
                tags=["c2"],
                when_to_use=[
                    "Starting a fresh C2 engagement — first Sliver call per deploy.",
                    "After system reboot — sliver-server does not auto-restart.",
                    "Want unattended daemon-mode operation (default).",
                ],
                when_not_to_use=[
                    "Server already running — call sliver_server_status first.",
                    "Ephemeral CI / container without persistent ~/.sliver — state won't survive.",
                    "Host has no outbound network — listener registration works but implant "
                    "callbacks won't reach you.",
                    "Multiple sliver-server instances on one host — they fight for the gRPC "
                    "port (31337) and fail to start.",
                ],
                prerequisites=[
                    "sliver-server binary installed (see BishopFox/sliver releases).",
                    "Writable ~/.sliver/ for certs — first run creates ~200 MB of CA + keys.",
                    "gRPC port 31337 and any intended listener ports free (e.g. 80/443).",
                ],
                follow_ups=[
                    "Wait ~30s on first start for cert init — poll sliver_server_status.",
                    "Create a per-operator config via sliver_run_command 'new-operator ...' "
                    "before sharing with teammates.",
                    "Register listeners (https/mtls/dns) via sliver_run_command before "
                    "generating implants.",
                ],
                pitfalls=[
                    "First start takes 30+ seconds for cert init; subsequent starts < 5s. "
                    "Don't retry during init or you'll race on .sliver/.",
                    "Server persists across sliver-client disconnects — remember to call "
                    "sliver_stop_server at engagement end or you leak a C2.",
                    "Windows uses CTRL_BREAK for shutdown (not SIGTERM); launched in a new "
                    "process group by design.",
                    "If ~/.sliver is corrupted, server fails silently — inspect the .log file "
                    "next to the PID file.",
                ],
                local_model_hints=(
                    "Call this ONCE per engagement. If unsure whether server is already up, "
                    "use sliver_server_status first — don't retry start."
                ),
                example_conversation=(
                    'User: "spin up my C2"\n'
                    "Agent -> sliver_server_status (first, expect running=false)\n"
                    '          -> sliver_start_server({"daemon": true})\n'
                    "Response: 'PID 1234, logs at ~/.kestrel/runs/sliver-server.pid.log'\n"
                    "Agent waits 30s then sliver_server_status again to confirm init."
                ),
            ),
>>>>>>> REPLACE
```

### Step 2 — REPLACE sliver_stop_server ToolSpec

```
REPLACE src/kestrel_mcp/tools/sliver_tool.py
<<<<<<< SEARCH
            ToolSpec(
                name="sliver_stop_server",
                description="Stop the sliver-server process started by this MCP.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop_server,
                tags=["c2"],
            ),
=======
            ToolSpec(
                name="sliver_stop_server",
                description=(
                    "Stop the sliver-server process whose PID was recorded by "
                    "sliver_start_server. Won't touch a server launched outside MCP."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_stop_server,
                tags=["c2"],
                when_to_use=[
                    "End of engagement — clean up running C2 cleanly.",
                    "Before host reboot / maintenance for a graceful shutdown.",
                    "Server is misbehaving and you want a clean restart.",
                ],
                when_not_to_use=[
                    "Active implants/sessions exist — stopping kills them all with no grace "
                    "period. Run sliver_list_sessions first.",
                    "Other operators are mid-engagement on this server.",
                    "Server was NOT started by this MCP — only the pid-file-tracked one stops.",
                ],
                prerequisites=[
                    "PID file exists at ~/.kestrel/runs/sliver-server.pid (set by start).",
                    "Current user can signal that PID (same uid, or CTRL_BREAK rights on Windows).",
                ],
                follow_ups=[
                    "Verify shutdown with sliver_server_status (running=false).",
                    "Archive the .log next to the PID file into engagement artifacts before the "
                    "next start rotates it.",
                ],
                pitfalls=[
                    "Stop kills ALL implants/sessions/listeners with no grace window.",
                    "Stale PID file with dead process returns ok without action.",
                    "Windows: needs CTRL_BREAK_EVENT into the server's process group, which "
                    "sliver_start_server sets up via CREATE_NEW_PROCESS_GROUP — don't bypass.",
                    "Second call after success is a no-op (PID file already removed).",
                ],
                local_model_hints=(
                    "This stops ONLY the server YOU started via sliver_start_server. "
                    "Won't kill an externally-launched sliver-server."
                ),
            ),
>>>>>>> REPLACE
```

### Step 3 — REPLACE sliver_server_status ToolSpec

```
REPLACE src/kestrel_mcp/tools/sliver_tool.py
<<<<<<< SEARCH
            ToolSpec(
                name="sliver_server_status",
                description="Return whether sliver-server is running (PID-file based).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_server_status,
                tags=["c2", "meta"],
            ),
=======
            ToolSpec(
                name="sliver_server_status",
                description=(
                    "Return whether the MCP-started sliver-server is running. "
                    "PID-file + signal-0 probe; does NOT verify gRPC responsiveness."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_server_status,
                tags=["c2", "meta"],
                when_to_use=[
                    "Before any Sliver operation — verify the server is up.",
                    "Troubleshooting 'connection refused' errors from sliver_run_command.",
                    "Waiting for first-run cert init to finish (poll every few seconds).",
                ],
                prerequisites=[],
                follow_ups=[
                    "running=true -> proceed with your intended Sliver op.",
                    "running=false -> sliver_start_server, or realise other Sliver calls will fail.",
                ],
                pitfalls=[
                    "Only checks PID-file presence + process alive — a zombied server may "
                    "report running=true but refuse gRPC calls. If commands fail despite "
                    "running=true, stop+start the server.",
                    "Stale PID file from a crashed server is auto-cleaned (reports running=false).",
                    "Does not see sliver-server processes launched outside this MCP.",
                ],
                local_model_hints=(
                    "Cheap and fast (< 100 ms). ALWAYS call before heavy Sliver ops to avoid "
                    "wasting a 5-minute command timeout when the server is down."
                ),
            ),
>>>>>>> REPLACE
```

### Step 4 — REPLACE sliver_run_command ToolSpec

```
REPLACE src/kestrel_mcp/tools/sliver_tool.py
<<<<<<< SEARCH
            ToolSpec(
                name="sliver_run_command",
                description=(
                    "Execute ONE raw sliver-client command and return stdout. "
                    "Useful for commands not covered by dedicated tools. "
                    "Example: 'implants', 'sessions', 'jobs', 'canaries'."
                ),
                input_schema={
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The sliver operator command line.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_run_command,
                dangerous=True,
                tags=["c2", "power-user"],
            ),
=======
            ToolSpec(
                name="sliver_run_command",
                description=(
                    "Execute ONE raw sliver-client operator command and return stdout. "
                    "Escape hatch for commands not covered by dedicated tools "
                    "(e.g. 'canaries', 'operators', 'armory install ...', 'update')."
                ),
                input_schema={
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": (
                                "Full sliver operator command line (what you'd type at the "
                                "sliver> prompt). NOT a shell command. e.g. 'https --domain "
                                "c2.example.com --lport 443'."
                            ),
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1800,
                            "description": (
                                "Maximum wall time in seconds. Default comes from "
                                "execution.timeout_sec (300). Bump for 'armory install' (> 60s) "
                                "or 'update' (may pull large artifacts)."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_run_command,
                dangerous=True,
                tags=["c2", "power-user"],
                when_to_use=[
                    "A dedicated tool doesn't exist for what you need (e.g. armory, canaries, "
                    "operators, update).",
                    "Debugging — 'help', 'version', 'sessions -h' etc.",
                    "One-off admin tasks: creating operator configs, registering listeners.",
                ],
                when_not_to_use=[
                    "Dedicated tool exists — use sliver_list_sessions over "
                    "sliver_run_command('sessions'); use sliver_list_listeners over 'jobs'.",
                    "Session-scoped ops ('use <id>; whoami') — use sliver_execute_in_session "
                    "instead; it validates session id and audits properly.",
                    "Command string contains cleartext secrets — first 200 chars are logged to "
                    "audit.log.",
                    "Need structured output (table parsed to JSON) — this returns raw stdout only.",
                ],
                prerequisites=[
                    "sliver-client binary resolvable (`kestrel doctor` checks).",
                    "Operator config in ~/.sliver-client/configs/ or tools.sliver.operator_config "
                    "set in settings.",
                    "sliver_server_status -> running=true.",
                ],
                follow_ups=[
                    "If the command was stateful (listener registration, implant generation), "
                    "verify the change via sliver_list_listeners or sliver_list_sessions.",
                    "For frequently-used commands, ask the author to add a dedicated tool — "
                    "structured output is always better than raw stdout parsing.",
                ],
                pitfalls=[
                    "No scope enforcement beyond what the operator config permits — this is a "
                    "raw shell into the server.",
                    "Output is raw stdout in the structured.stdout field; ASCII tables are NOT "
                    "parsed (use sliver_list_sessions/_listeners for parsed rows).",
                    "Long-running commands may hit timeout_sec and leave partial state.",
                    "gRPC drop mid-call loses stdout; no retry.",
                ],
                local_model_hints=(
                    "Escape hatch. ALWAYS check whether a dedicated tool covers the intent before "
                    "calling this. Command string is the sliver> prompt input, not a shell "
                    "command. Audit log captures first 200 chars — don't embed credentials."
                ),
                example_conversation=(
                    'User: "register an HTTPS listener on 443 for c2.example.com"\n'
                    "Agent -> sliver_run_command({\n"
                    '    "command": "https --domain c2.example.com --lport 443"\n'
                    "})\n"
                    "Response: 'Started HTTPS listener: 1 (0.0.0.0:443)'\n"
                    "Agent follows up with sliver_list_listeners to confirm id + config."
                ),
            ),
>>>>>>> REPLACE
```

### Step 5 — WRITE test file (new, first sliver test)

```
WRITE tests/unit/tools/test_sliver_tool.py
```
```python
"""Tests for the Sliver tool module.

Starts as a regression guard for RFC-B05b1 (guidance completeness on server
lifecycle + run_command). B05b2 will expand to cover the remaining 4 ops
tools; handler-level tests live outside this RFC's scope.
"""

from __future__ import annotations

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.sliver_tool import SliverModule


def _specs_by_name() -> dict[str, object]:
    module = SliverModule(Settings(), ScopeGuard([]))
    return {spec.name: spec for spec in module.specs()}


# Tools covered by RFC-B05b1. B05b2 will extend this set.
B05B1_TOOLS = (
    "sliver_start_server",
    "sliver_stop_server",
    "sliver_server_status",
    "sliver_run_command",
)


async def test_sliver_b1_tools_exist():
    specs = _specs_by_name()
    for name in B05B1_TOOLS:
        assert name in specs, f"{name} missing from SliverModule.specs()"


async def test_sliver_b1_dangerous_tools_carry_full_guidance():
    """Dangerous tools get ALL guidance fields populated (RFC-B05b1).

    Non-dangerous server-status/stop have looser requirements (see the next test).
    """

    specs = _specs_by_name()
    dangerous_names = {"sliver_start_server", "sliver_run_command"}
    required = (
        "when_to_use",
        "when_not_to_use",
        "prerequisites",
        "follow_ups",
        "pitfalls",
    )
    for name in dangerous_names:
        spec = specs[name]
        assert spec.dangerous, f"{name}: expected dangerous=True."
        for field_name in required:
            assert getattr(spec, field_name), (
                f"{name}: guidance field '{field_name}' is empty (RFC-B05b1)."
            )
        assert spec.local_model_hints, f"{name}: local_model_hints missing."
        assert spec.example_conversation, (
            f"{name}: dangerous tools must ship an example_conversation."
        )


async def test_sliver_b1_nondangerous_tools_carry_core_guidance():
    """Non-dangerous tools still need when_to_use + local_model_hints + pitfalls."""

    specs = _specs_by_name()
    for name in ("sliver_stop_server", "sliver_server_status"):
        spec = specs[name]
        assert not spec.dangerous, f"{name}: unexpectedly dangerous."
        assert spec.when_to_use, f"{name}: when_to_use is empty."
        assert spec.local_model_hints, f"{name}: local_model_hints missing."
        assert spec.pitfalls, f"{name}: pitfalls missing."


async def test_sliver_b1_all_schema_props_have_descriptions():
    specs = _specs_by_name()
    for name in B05B1_TOOLS:
        spec = specs[name]
        props = spec.input_schema.get("properties") or {}
        for prop_name, prop_def in props.items():
            assert "description" in prop_def and prop_def["description"].strip(), (
                f"{name}.{prop_name}: missing input_schema description (RFC-B05b1)."
            )
```

### Step 6 — INDEX row + CHANGELOG entry

```
REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-B05a | Tool guidance — Impacket         | done   | RFC-002     | coordinator |
=======
| RFC-B05a | Tool guidance — Impacket         | done   | RFC-002     | coordinator |
| RFC-B05b1 | Tool guidance — Sliver server   | open   | RFC-002     | coordinator |
>>>>>>> REPLACE
```

```
APPEND CHANGELOG.md

### Tool guidance hardening — Sliver server + run_command (RFC-B05b1)
- `src/kestrel_mcp/tools/sliver_tool.py`:
  - `sliver_start_server` (dangerous): full guidance block covering cert-init
    30s first-start, gRPC port 31337 collision, ~/.sliver persistence,
    per-operator config follow-up.
  - `sliver_stop_server`: stealth/session-loss warnings, Windows CTRL_BREAK
    caveat, pid-file semantics, explicit "only stops MCP-started servers"
    note.
  - `sliver_server_status`: cheap-call hint, PID-probe vs gRPC-responsive
    distinction, polling guidance for first-run cert init.
  - `sliver_run_command` (dangerous, power-user): escape-hatch guidance,
    audit-log 200-char truncation warning, explicit "prefer dedicated tools"
    direction, parsed-table vs raw-stdout difference.
  - Schema params `command` and `timeout_sec` gain proper descriptions.
- `tests/unit/tools/test_sliver_tool.py` (new, first Sliver test file):
  - Regression guard covering guidance completeness for the 4 B05b1 tools.
  - Distinguishes dangerous (full guidance + example) vs non-dangerous
    (core guidance) requirements.
- Follow-up RFC-B05b2 will extend the test to all 8 tools once
  list_sessions/list_listeners/generate_implant/execute_in_session are
  documented.
```

### Step 7 — verify_cmd

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_sliver_tool.py -v
```

### Step 8 — regression

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

Step 5 含 4 个测试：
- `test_sliver_b1_tools_exist` — sanity, B05b1 4 tools 都在
- `test_sliver_b1_dangerous_tools_carry_full_guidance` — dangerous tools
  全 guidance + example_conversation
- `test_sliver_b1_nondangerous_tools_carry_core_guidance` — 核心字段
  (when_to_use/pitfalls/local_model_hints)
- `test_sliver_b1_all_schema_props_have_descriptions` — 所有 4 个 tool
  的 input_schema properties 都有 description

## Post-checks

- [ ] `git diff --stat` 只列 `files_will_touch` 的 5 个文件
- [ ] `pytest tests/unit/tools/test_sliver_tool.py` 4 passed
- [ ] `full_verify.py` 仍 8/8（runtime 行为零变化）
- [ ] `kestrel list-tools | findstr sliver_` 列出 8 个 sliver tools（b1 后 4 个
      带新 guidance，b2 的 4 个保持旧状态直到下一 RFC）
- [ ] Post-commit sanity: `git status Count: 0`

## Rollback plan

见 front-matter。纯 data / schema-description 改动，无 DB / 外部副作用。

## Updates to other docs

- `CHANGELOG.md` 见 Step 6
- `rfcs/INDEX.md` 加 B05b1 一行
- 不改 TOOLS_MATRIX（工具身份未变）

## Notes for executor

- **Budget note**: declared at hard cap (400). Actual git insertions in
  the commit will exceed 400 because the RFC spec file inline-duplicates
  the 4 REPLACE blocks (~90 lines each). This mirrors the H01 precedent:
  the declared budget is aspirational, the executor ships the full work
  in one atomic commit. Coordinator-approved.
- **SEARCH 块精确度**：4 个 ToolSpec 目前全无 guidance fields；原 literal 从
  `ToolSpec(` 到对应闭合的 `),`。复制 SEARCH 时必须**包含闭合的 `),`**，否则
  匹配会延伸到下一个 ToolSpec。
- **`requires_scope_field` 保持未设**：b1 的 4 个 tools 都是 server-level，
  不针对 target。只有 b2 的 generate_implant 有 `requires_scope_field="callback_addr"`。
- **pytest-asyncio auto mode**：新 test 写 `async def`，即使函数体是 sync 逻辑
  （pytest-asyncio 1.3+ 在 auto mode 下对 sync def 会 warn）。
- **不加 handler smoke tests**：那是独立 hardening work，脱离本 RFC scope。
  `test_sliver_tool.py` 只做 guidance regression。未来日常开发加 handler test
  自然扩展 file.
- **SliverModule 实例化无 I/O**：构造函数只读 settings、创建 runs_dir（已存在
  时 no-op）。test fixture 直接 `SliverModule(Settings(), ScopeGuard([]))` 即可。

## Changelog

- **2026-04-21 v1.0** — Initial spec authored by coordinator.
  First of the B05b series (Sliver). B05b2 (4 remaining ops tools) as
  follow-up.
