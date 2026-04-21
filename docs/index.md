# Kestrel MCP

Kestrel MCP is a scope-gated Model Context Protocol server for authorized
security teams. It wraps recon, web, AD, and reporting tools behind a single
audited interface.

## Start Here

- Read the project overview in the top-level [README](../README.md).
- Review the [security policy](../SECURITY.md) before operating tools.
- Use the [tools matrix](../TOOLS_MATRIX.md) to understand supported binaries.
- Follow [releasing](releasing.md) for tag-driven PyPI, GHCR, and GitHub
  Release publishing.

## Local Preview

```powershell
uv sync --frozen --all-extras
uv run --no-sync mkdocs serve
```
