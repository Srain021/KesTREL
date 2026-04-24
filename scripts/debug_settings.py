"""Tiny debug helper: print effective Settings from config + env."""

from __future__ import annotations

import os

from redteam_mcp.config import load_settings


def main() -> None:
    env_keys = sorted(k for k in os.environ if k.startswith("REDTEAM_MCP_"))
    print("Active REDTEAM_MCP_* env vars:")
    for k in env_keys:
        print(f"  {k}={os.environ[k]!r}")
    if not env_keys:
        print("  (none)")
    print()

    settings = load_settings()
    print(f"security.authorized_scope = {settings.security.authorized_scope}")
    print(f"security.dry_run          = {settings.security.dry_run}")
    print()
    print("Tool enablement:")
    for name in ("shodan", "nuclei", "caido", "evilginx", "sliver", "havoc", "ligolo"):
        block = getattr(settings.tools, name)
        binary = getattr(block, "binary", None)
        print(f"  {name:10s} enabled={block.enabled}  binary={binary}")


if __name__ == "__main__":
    main()
