"""Register the Red-Team MCP server with Cursor.

Usage:
    python scripts/register_cursor.py [--python-exe PATH] [--scope SCOPE] [--force]

Behaviour:
    * Locates (or creates) ``~/.cursor/mcp.json``.
    * Adds an entry named ``kestrel-mcp`` pointing at the current Python's
      ``python -m kestrel_mcp serve`` launch.
    * Pre-populates environment variables from the current shell so Shodan
      and tool paths are picked up automatically.
    * Idempotent: re-running updates the existing entry unless ``--force``
      is needed to overwrite a conflicting config.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


CURSOR_MCP_FILE = Path.home() / ".cursor" / "mcp.json"
SERVER_KEY = "kestrel-mcp"


def main() -> int:
    parser = argparse.ArgumentParser(description="Register kestrel-mcp with Cursor")
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Python interpreter that has kestrel-mcp installed.",
    )
    parser.add_argument(
        "--scope",
        default=os.environ.get("KESTREL_MCP_AUTHORIZED_SCOPE", ""),
        help="Initial authorized scope (comma-separated).",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing entry.")
    args = parser.parse_args()

    CURSOR_MCP_FILE.parent.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if CURSOR_MCP_FILE.is_file():
        raw = CURSOR_MCP_FILE.read_text("utf-8").strip()
        if raw:
            try:
                config = json.loads(raw)
            except json.JSONDecodeError as exc:
                if not args.force:
                    sys.exit(
                        f"Existing {CURSOR_MCP_FILE} is not valid JSON: {exc}\n"
                        "Re-run with --force to overwrite it."
                    )
                print(f"[warn] overwriting malformed {CURSOR_MCP_FILE}")

    servers = config.setdefault("mcpServers", {})
    if SERVER_KEY in servers and not args.force:
        print(f"[info] '{SERVER_KEY}' already present in {CURSOR_MCP_FILE}; updating.")

    entry = {
        "command": args.python_exe,
        "args": ["-m", "kestrel_mcp", "serve"],
        "env": {
            "KESTREL_MCP_AUTHORIZED_SCOPE": args.scope,
            "SHODAN_API_KEY": os.environ.get("SHODAN_API_KEY", ""),
            "PYTHONUNBUFFERED": "1",
        },
    }
    for env_key in (
        "KESTREL_MCP_TOOL_NUCLEI",
        "KESTREL_MCP_TOOL_SLIVER_SERVER",
        "KESTREL_MCP_TOOL_SLIVER_CLIENT",
        "KESTREL_MCP_TOOL_LIGOLO_PROXY",
        "KESTREL_MCP_TOOL_CAIDO_CLI",
        "KESTREL_MCP_TOOL_EVILGINX",
        "KESTREL_MCP_TOOL_HAVOC",
    ):
        if value := os.environ.get(env_key):
            entry["env"][env_key] = value

    servers[SERVER_KEY] = entry

    CURSOR_MCP_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[ok] Registered '{SERVER_KEY}' in {CURSOR_MCP_FILE}")
    print(f"      command: {entry['command']} {' '.join(entry['args'])}")
    if not args.scope:
        print("[warn] KESTREL_MCP_AUTHORIZED_SCOPE is empty — offensive tools will refuse to run")
        print("       until you set it. Pass --scope or export the env variable.")
    if not entry["env"].get("SHODAN_API_KEY"):
        print("[warn] SHODAN_API_KEY is empty — Shodan tools will return an error.")

    if which := shutil.which("nuclei"):
        print(f"[info] Found nuclei on PATH: {which}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
