# Quickstart

This page is the short path from clone to a running Kestrel MCP server.

For the full Chinese operator guide, use [Chinese Manual](user-manual.zh-CN.md).

## Install

```bash
git clone https://github.com/Srain021/KesTREL.git
cd KesTREL
uv sync --frozen --all-extras
```

## Configure

Use either `kestrel.yaml`:

```yaml
security:
  authorized_scope:
    - "*.lab.internal"
    - "192.168.56.0/24"

tools:
  nuclei:
    binary: "C:/Users/YOU/hacking-tools/nuclei.exe"
  nmap:
    binary: "C:/Program Files (x86)/Nmap/nmap.exe"
```

Or environment variables:

```powershell
$env:KESTREL_MCP_SECURITY__AUTHORIZED_SCOPE="*.lab.internal,192.168.56.0/24"
$env:SHODAN_API_KEY="REPLACE_WITH_YOUR_KEY"
$env:KESTREL_MCP_TOOLS__NUCLEI__BINARY="C:/Users/YOU/hacking-tools/nuclei.exe"
```

Use the nested `KESTREL_MCP_SECURITY__...` and `KESTREL_MCP_TOOLS__...` form.

## Verify

```bash
kestrel doctor
kestrel show-config
kestrel list-tools
```

## Run

```bash
kestrel serve
```

If you want the full bundled preset:

```bash
kestrel --edition internal serve
```

HTTP transport:

```powershell
$env:KESTREL_MCP_HTTP_TOKEN="change-me"
kestrel serve-http --host 127.0.0.1 --port 8765 --endpoint /mcp
```

## Connect A Client

Start from the shipped Cursor example:

- [config/cursor-mcp.json.example](https://github.com/Srain021/KesTREL/blob/main/config/cursor-mcp.json.example)

## Next

- [Chinese Manual](user-manual.zh-CN.md)
- [Internal Firepower](internal-firepower.md)
- [Reference](reference.md)
