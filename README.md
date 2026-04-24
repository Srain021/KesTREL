# Red-Team MCP Server

**Expose 40+ offensive-security tools to any MCP-speaking LLM (Cursor, Claude Desktop, Cline, Continue, Zed) behind a single, audit-logged, scope-gated interface.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/) [![MCP 1.2+](https://img.shields.io/badge/MCP-1.2%2B-purple)](https://modelcontextprotocol.io/) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> ⚠️ **Authorized use only.** See [LICENSE](LICENSE) for the full responsible-use clause. Running this against systems you do not own or have written permission to test is a crime in most jurisdictions.

---

## ✨ What you get

| Tool | Wraps | LLM-callable actions |
|------|-------|----------------------|
| **Shodan** | Python SDK | search, host, count, facets, scan, account-info |
| **Nuclei** | `nuclei` binary (JSONL output) | scan, update-templates, list-templates, validate-template, version |
| **Subfinder** | `subfinder` binary | enum, version |
| **httpx** | `httpx` binary | probe, version |
| **Nmap** | `nmap` binary | scan, os-detect, version |
| **ffuf** | `ffuf` binary | dir-bruteforce, param-fuzz, version |
| **Impacket** | `impacket` Python lib | psexec, smbexec, wmiexec, secretsdump, get-user-spns |
| **BloodHound** | BloodHound-CE REST | query, list-datasets, version |
| **Caido** | CLI / REST (phase 2) | start, stop, status, replay *(limited: intercept-config not yet exposed)* |
| **Evilginx** | CLI (phase 3) | start, stop, status, list-phishlets, list-sessions, enable-phishlet, create-lure |
| **Sliver** | gRPC client (phase 3) | start-server, stop, status, listeners, sessions, generate-implant, execute-in-session, upload-file, download-file |
| **Havoc** | CLI (phase 3) | build, start-teamserver, stop, status, lint-profile *(limited: generate-demon is hint-only, execute not yet implemented)* |
| **Ligolo-ng** | CLI (phase 2) | start-proxy, stop, status, add-route, list-agents, tunnel-status |
| **Readiness** | native Python | doctor, exploitability-triage, attack-path-plan, operator-fire-control, zero-day-hypothesis, evidence-pack |
| **Engagement** | native Python + DB | new, list, show, activate, pause, close, switch, scope-add/remove/list/check, target-add/list, finding-list/show/transition |
| **Workflows** | native Python (phase 3) | `recon_target` ✅, `generate_pentest_report` ✅, `full_vuln_scan` ✅, `exploit_chain` ✅ |

All tools share one cross-cutting design:

* **Scope enforcement** — every offensive tool consults a central `ScopeGuard` before hitting a target. Empty scope = refuse all offensive actions by default.
* **Audit log** — every `call_tool` invocation is written to `~/.kestrel/audit.log` as a structured JSON record.
* **Dry-run mode** — `--dry-run` or `KESTREL_MCP_DRY_RUN=1` turns every offensive command into a no-op that still returns the argv it *would* have run.
* **Timeouts + output caps** — no tool can exhaust memory or hang forever.
* **JSON Schema inputs** — each tool advertises a strict JSON schema so LLMs can validate arguments before calling.

---

## 🚀 Quickstart

### 1. Install

**Windows (PowerShell):**

```powershell
git clone https://github.com/your-org/kestrel-mcp.git
cd kestrel-mcp
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

**macOS / Linux:**

```bash
git clone https://github.com/your-org/kestrel-mcp.git
cd kestrel-mcp
./scripts/install.sh
```

Or manually with any Python 3.10+:

```bash
pip install -e ".[dev]"
```

### Reproducible installs (recommended)

We use [uv](https://github.com/astral-sh/uv) to pin every transitive dependency.
The committed `uv.lock` file guarantees byte-identical installs across
developers, CI, and production.

```bash
pip install uv
uv sync --frozen --all-extras
```

See [RFC-001](./rfcs/RFC-001-uv-lock-dependencies.md) for the rationale.

### 2. Configure

Copy and edit the environment template:

```bash
cp .env.example .env
```

Minimum fields to set:

```bash
# Engagement authorization — COMMA-SEPARATED list of:
#   • exact hostnames          host.example.com
#   • wildcard hostnames       *.example.com
#   • CIDR ranges              10.0.0.0/16
#   • single IPs               10.0.0.1
KESTREL_MCP_AUTHORIZED_SCOPE="*.lab.internal,192.168.56.0/24"

# Required if you want to use Shodan tools
SHODAN_API_KEY="your-shodan-key"

# Optional tool binary overrides (auto-detected from PATH otherwise)
KESTREL_MCP_TOOL_NUCLEI="C:/Users/you/hacking-tools/nuclei.exe"
```

### 3. Verify readiness

```bash
kestrel-mcp doctor
```

This prints a table showing which tools are enabled, whether their binaries are found, and whether the Shodan key + scope are set.

### 4. Run the server

```bash
kestrel-mcp serve
```

(No args = the same thing — this is stdio transport that MCP hosts launch on demand.)

### 5. Register with Cursor

```bash
python scripts/register_cursor.py --scope "*.lab.internal,192.168.56.0/24"
```

That writes `~/.cursor/mcp.json`. Restart Cursor, open a chat, and type:

> "Run a Shodan search for `product:nginx country:US` and show me the top 5 hits."

Cursor will auto-invoke `shodan_search`.

---

## 🧑‍🤝‍🧑 Team Edition Quickstart

Team Edition is the unleashed mode for internal crews (see
[PRODUCT_LINES.md](./PRODUCT_LINES.md) Part 9). Get operational in one
command:

```powershell
# One-liner bootstrap
kestrel --edition team team bootstrap --name op-winter-2026 --scope "target.lab,*.internal"

# Then start the server, pointing your LLM client at stdio
kestrel --edition team serve
$env:KESTREL_ENGAGEMENT = "op-winter-2026"
```

What "unleashed" means in this edition:

- `scope_enforcement = warn_only` — out-of-scope targets are logged, not
  blocked (see RFC-T00).
- `rate_limit_enabled = false` — no throttling of tool calls.
- `credential_encryption_required = false` — Team may store plaintext-at-rest
  credentials in the vault for crew sharing; Pro keeps encrypted-at-rest
  storage by default.

Switch back to Pro strict defaults by dropping `--edition team` or setting
`KESTREL_EDITION=pro`.

---

## Internal Firepower Edition

For private crew operations where the operator wants the full bundled tool
surface enabled at startup, use the dedicated `internal` edition:

```powershell
kestrel --edition internal show-config
kestrel --edition internal team bootstrap --name op-firepower --scope "target.lab,*.internal"
kestrel --edition internal serve
```

`internal` keeps the Team-style operational defaults (`scope_enforcement =
warn_only`, rate limits off, long-running tools allowed) and additionally
enables all bundled tool modules by default: Shodan, Nuclei, Subfinder, httpx,
Nmap, ffuf, Impacket, BloodHound, Caido, Evilginx, Sliver, Havoc, and Ligolo.

Use this only for authorized internal/lab work. The readiness and fire-control
tools remain the human approval layer for high-risk actions.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  LLM Client (Cursor / Claude Desktop / Cline / Zed)     │
└──────────────────────────┬──────────────────────────────┘
                           │ JSON-RPC over stdio
┌──────────────────────────▼──────────────────────────────┐
│  kestrel_mcp.server.RedTeamMCPServer                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Scope guard • audit log • dry-run • timeout     │   │
│  └────┬───────┬──────┬──────┬──────┬──────┬──────┬──┘   │
│       │       │      │      │      │      │      │      │
│  ┌────▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐   │
│  │Shodan │ │Nucl│ │Cai-│ │Evil│ │Sli-│ │Hav-│ │Lig-│   │
│  │ API   │ │ei  │ │do  │ │ginx│ │ver │ │oc  │ │olo │   │
│  └───────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘   │
└─────────────────────────────────────────────────────────┘
```

Every tool module subclasses `ToolModule` and returns a list of `ToolSpec`. The server:

1. Calls `load_modules()` to discover enabled modules.
2. Registers each `ToolSpec` under its unique `name`.
3. On every `call_tool`:
   - validates scope (if `requires_scope_field` is set),
   - writes an audit record,
   - hands the arguments to the async handler,
   - renders the `ToolResult` as text + JSON blocks.

Adding a new tool is ~30 lines: subclass `ToolModule`, return a `ToolSpec`, register in `tools/__init__.py`.

---

## 📖 Configuration Layers

Resolution order (later wins):

1. `config/default.yaml` — shipped defaults.
2. `~/.kestrel/config.yaml` — per-user overrides.
3. `./kestrel.yaml` — per-project overrides.
4. Environment variables prefixed `KESTREL_MCP_`.
5. `--config PATH` CLI override.

Full surface:

```yaml
server:
  name: "kestrel-mcp"
  version: "0.1.0"

security:
  authorized_scope: []
  require_ack: true
  dry_run: false
  audit_log: "~/.kestrel/audit.log"

execution:
  timeout_sec: 300
  max_output_bytes: 5242880
  working_dir: "~/.kestrel/runs"

logging:
  level: "INFO"
  format: "json"
  dir: "~/.kestrel/logs"

tools:
  shodan:
    enabled: true
    api_key_env: "SHODAN_API_KEY"
  nuclei:
    enabled: true
    binary: null
    default_rate_limit: 150
  caido: { enabled: false }
  evilginx: { enabled: false }
  sliver: { enabled: false }
  havoc: { enabled: false }
  ligolo: { enabled: false }
```

---

## 🛠️ CLI reference

```
kestrel-mcp serve           # default, stdio MCP server
kestrel-mcp serve --dry-run # never actually exec offensive tools
kestrel-mcp serve --scope "*.lab.internal,10.0.0.0/8"
kestrel-mcp doctor          # readiness report
kestrel-mcp list-tools      # dump MCP tool schema as JSON
kestrel-mcp version
```

---

## 🧪 Example LLM prompts

Once Cursor is wired up, you can say:

> **"Run `shodan_count` for `product:redis -requirepass country:CN`."**
> → Returns an integer. 0 credits consumed.
>
> **"Do a light Nuclei scan on `https://app.lab.internal` with only `critical,high` severity."**
> → Runs `nuclei_scan` with your scope enforced; returns structured findings.
>
> **"Update the Nuclei template library."**
> → Calls `nuclei_update_templates`.
>
> **"What's my Shodan account status?"**
> → Calls `shodan_account_info`.

The LLM handles tool choice, argument filling, and result summarization.

---

## 🔐 Security model

This project takes a paranoid stance on scope enforcement:

* **Empty scope = refuse all offensive tools.** The very first tool call with `authorized_scope=[]` raises `AuthorizationError`. You cannot forget to set scope.
* **CIDR + wildcard aware.** `192.168.0.0/16` and `*.example.com` are both first-class.
* **Audit-first.** Every call writes an `audit=True` JSON log line with tool name, argument keys, duration, exit code, and result size.
* **No eval, no shell.** All subprocesses use `argv` arrays — no shell interpolation, no injection surface via tool arguments.
* **Subprocess output cap.** Default 5 MiB; beyond that the result is truncated and flagged.

Known limits (documented, not fixed): the scope guard can't verify the *true* target of every deep URL (Nuclei can follow redirects off-scope); the audit log is not tamper-proof. For high-assurance engagements, ship the audit log to a central SIEM.

---

## 🧱 Adding a new tool

1. **Create the module**:

   ```python
   # src/kestrel_mcp/tools/mytool_tool.py
   from .base import ToolModule, ToolSpec, ToolResult

   class MyToolModule(ToolModule):
       id = "mytool"

       def specs(self):
           return [
               ToolSpec(
                   name="mytool_do_thing",
                   description="Do the thing.",
                   input_schema={"type": "object", "properties": {"arg": {"type": "string"}}},
                   handler=self._handle_do,
               )
           ]

       async def _handle_do(self, args):
           return ToolResult(text="done", structured={"input": args})
   ```

2. **Register it** in `src/kestrel_mcp/tools/__init__.py`.

3. **Add config block** to `config/default.yaml`:

   ```yaml
   tools:
     mytool:
       enabled: true
   ```

4. `kestrel-mcp doctor` should now show it.

---

## 🗺️ Roadmap

* [x] Phase 1 — core server, Shodan, Nuclei, CLI, install scripts
* [x] Phase 2 — Ligolo-ng, Caido
* [x] Phase 3 — Sliver, Havoc, Evilginx
* [x] Phase 4 — workflow tools (`recon_target`, `full_vuln_scan`, `exploit_chain`, `generate_pentest_report`)
* [x] Phase 5 — MCP Resources + Prompts library
* [ ] Phase 6 — PyPI release + Docker image

---

## 📜 License

MIT + responsible-use clause. See [LICENSE](LICENSE).

Using this software is acknowledgement that:

* You will only use it against systems you own or have written authorization to test.
* You understand that unauthorized access is a crime (CFAA / 中国刑法 285-286 / CMA 1990 / GDPR Art.32).
* The authors accept no liability for your actions.
