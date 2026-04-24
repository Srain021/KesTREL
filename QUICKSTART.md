# Quickstart

This is the shortest path from clone to a working MCP server.

For the full operator guide, use [docs/user-manual.zh-CN.md](./docs/user-manual.zh-CN.md).

## 1. Install

```bash
git clone https://github.com/Srain021/KesTREL.git
cd KesTREL
uv sync --frozen --all-extras
```

## 2. Set scope and tool paths

Use either `kestrel.yaml` in the repo root:

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
  httpx:
    binary: "C:/Users/YOU/hacking-tools/httpx.exe"
  nmap:
    binary: "C:/Program Files (x86)/Nmap/nmap.exe"
```

Or environment variables:

```powershell
$env:KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE="*.lab.internal,192.168.56.0/24"
$env:SHODAN_API_KEY="REPLACE_WITH_YOUR_KEY"
$env:KESTREL_MCP_TOOLS__NUCLEI__BINARY="C:/Users/YOU/hacking-tools/nuclei.exe"
$env:KESTREL_MCP_TOOLS__SUBFINDER__BINARY="C:/Users/YOU/hacking-tools/subfinder.exe"
$env:KESTREL_MCP_TOOLS__HTTPX__BINARY="C:/Users/YOU/hacking-tools/httpx.exe"
$env:KESTREL_MCP_TOOLS__NMAP__BINARY="C:/Program Files (x86)/Nmap/nmap.exe"
```

Use the nested `KESTREL_MCP_SECURITY__...` and `KESTREL_MCP_TOOLS__...` form.
Older flat env names are no longer the recommended path.

## 3. Verify the install

```bash
kestrel doctor
kestrel show-config
kestrel list-tools
```

What you want to see:

- `Authorized scope` is not empty
- required binaries resolve to real paths
- `show-config` prints the expected edition and enabled tools

## 4. Run the server

Default strict preset:

```bash
kestrel serve
```

Full bundled internal preset:

```bash
kestrel --edition internal serve
```

HTTP transport for reverse-proxied access:

```powershell
$env:KESTREL_MCP_HTTP_TOKEN="change-me"
kestrel serve-http --host 127.0.0.1 --port 8765 --endpoint /mcp
```

## 5. Connect Cursor

Start from [`config/cursor-mcp.json.example`](./config/cursor-mcp.json.example).

The shipped example already uses:

- `python -m kestrel_mcp --edition internal serve`
- nested env variables
- common binary overrides for Windows lab setups

## 6. First useful flow

Create and activate an engagement:

```powershell
kestrel --edition team team bootstrap --name op-lab --scope "*.lab.internal,192.168.56.0/24"
$env:KESTREL_ENGAGEMENT="op-lab"
kestrel --edition internal serve
```

Then ask the client to run one of:

- `recon_target`
- `full_vuln_scan`
- `engagement_target_list`
- `engagement_finding_list`
- `resources/list`

## Common Misses

| Symptom | Cause | Fix |
| --- | --- | --- |
| `authorized_scope is empty` | Scope not configured | Set `KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE` or add `security.authorized_scope` to `kestrel.yaml` |
| Binary not found in `doctor` | Tool path missing or wrong | Set the matching `KESTREL_MCP_TOOLS__...__BINARY` value |
| HTTP server exits on startup | No token configured | Set `KESTREL_MCP_HTTP_TOKEN` or use `--allow-no-auth` for localhost-only labs |
| Cursor starts but tools fail | Wrong command or env layout | Rebase your config on `config/cursor-mcp.json.example` |
| Results do not show engagement data | No active engagement | Set `KESTREL_ENGAGEMENT` after bootstrap |
