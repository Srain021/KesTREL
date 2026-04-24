# Kestrel MCP

Scope-gated MCP server for authorized security work. It gives an MCP client one
audited surface for recon, scanning, web tooling, C2 helpers, engagement state,
resources, prompts, and reporting.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![MCP 1.2+](https://img.shields.io/badge/MCP-1.2%2B-black)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> Authorized use only. Run this only against systems you own or have written
> permission to test.

## Start Here

- [Quickstart](./QUICKSTART.md)
- [Chinese manual](./docs/user-manual.zh-CN.md)
- [Cursor MCP example](./config/cursor-mcp.json.example)
- [Security policy](./SECURITY.md)
- [Release guide](./docs/releasing.md)
- [Changelog](./CHANGELOG.md)

## What Ships In `v1.0.0`

| Area | Included |
| --- | --- |
| Core server | stdio MCP, Streamable HTTP MCP, scope guard, dry-run, readiness checks, structured logging |
| Audit trail | DB-backed `tool_invocation` records with chained hashes and argument redaction |
| Engagement state | engagements, scope entries, targets, findings, active engagement switching |
| Recon and validation | Shodan, Nuclei, Subfinder, Amass, httpx, Katana, Nmap, ffuf, sqlmap |
| Identity, AD, cracking | Impacket, NetExec, hashcat, BloodHound |
| Web and access | Caido, Evilginx, Ligolo-ng |
| C2 | Sliver, Havoc |
| Workflows | `recon_target`, `full_vuln_scan`, `web_app_deep_scan`, `exploit_chain`, `generate_pentest_report` |
| MCP extras | `resources/list`, `resources/read`, `prompts/list`, `prompts/get` |
| Extensibility | plugin entry points via `kestrel_mcp.plugins` |

## Editions

| Edition | Use case | Behavior |
| --- | --- | --- |
| `pro` | Default local or client-facing use | Strict scope enforcement and safer defaults |
| `team` | Internal crew operations | Team bootstrap flow and looser runtime defaults |
| `internal` | Private lab / crew setup | Team-style runtime plus all bundled tools enabled by default |

## 5-Minute Setup

### 1. Install

```bash
git clone https://github.com/Srain021/KesTREL.git
cd KesTREL
uv sync --frozen --all-extras
```

### 2. Configure scope and binaries

Use `kestrel.yaml` if you want repo-local settings:

```yaml
security:
  authorized_scope:
    - "*.lab.internal"
    - "192.168.56.0/24"

tools:
  nuclei:
    binary: "C:/Users/YOU/hacking-tools/nuclei.exe"
  subfinder:
    binary: "C:/Users/YOU/hacking-tools/subfinder.exe"
  amass:
    binary: "C:/Users/YOU/hacking-tools/amass.exe"
  httpx:
    binary: "C:/Users/YOU/hacking-tools/httpx.exe"
  katana:
    binary: "C:/Users/YOU/hacking-tools/katana.exe"
  sqlmap:
    binary: "C:/Users/YOU/hacking-tools/sqlmap.exe"
  netexec:
    binary: "C:/Users/YOU/hacking-tools/nxc.exe"
  hashcat:
    binary: "C:/Users/YOU/hacking-tools/hashcat.exe"
```

Or use environment variables with the current nested layout:

```powershell
$env:KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE="*.lab.internal,192.168.56.0/24"
$env:SHODAN_API_KEY="REPLACE_WITH_YOUR_KEY"
$env:KESTREL_MCP_TOOLS__NUCLEI__BINARY="C:/Users/YOU/hacking-tools/nuclei.exe"
$env:KESTREL_MCP_TOOLS__KATANA__BINARY="C:/Users/YOU/hacking-tools/katana.exe"
$env:KESTREL_MCP_TOOLS__SQLMAP__BINARY="C:/Users/YOU/hacking-tools/sqlmap.exe"
```

### 3. Verify

```bash
kestrel doctor
kestrel show-config
kestrel list-tools
```

### 4. Run

```bash
kestrel serve
```

If you want the full bundled tool preset:

```bash
kestrel --edition internal serve
```

### 5. Connect an MCP client

Use [`config/cursor-mcp.json.example`](./config/cursor-mcp.json.example) as the
base config for Cursor or another MCP host. The bundled example already uses
the current `python -m kestrel_mcp --edition internal serve` form and the
nested `KESTREL_MCP_*` env layout.

## Recommended First Flow

Bootstrap an engagement, set it active, then let the MCP client drive tools and
workflows against that context.

```powershell
kestrel --edition team team bootstrap --name op-lab --scope "*.lab.internal,192.168.56.0/24"
$env:KESTREL_ENGAGEMENT="op-lab"
kestrel --edition internal serve
```

Good first calls once the client is attached:

- `recon_target`
- `full_vuln_scan`
- `engagement_target_list`
- `engagement_finding_list`
- `resources/list`
- `prompts/list`

## HTTP Transport

For reverse-proxied team access, run the Streamable HTTP transport instead of
stdio:

```powershell
$env:KESTREL_MCP_HTTP_TOKEN="change-me"
kestrel serve-http --host 127.0.0.1 --port 8765 --endpoint /mcp
```

Keep it behind localhost or a trusted reverse proxy. The HTTP server expects a
Bearer token unless `--allow-no-auth` is set.

## Documentation Map

- [Quickstart](./QUICKSTART.md)
- [Chinese manual](./docs/user-manual.zh-CN.md)
- [Internal Firepower](./docs/internal-firepower.md)
- [Tools Matrix](./TOOLS_MATRIX.md)
- [RFC index](./rfcs/INDEX.md)
- [Release guide](./docs/releasing.md)

## Status

The Phase 1-5 baseline is in place and the repo is at `1.0.0`. The remaining
release work is packaging and publishing:

- tag the release
- publish PyPI artifacts
- publish GHCR image
- cut the GitHub Release notes

## License

MIT plus the responsible-use clause in [LICENSE](./LICENSE).
