"""Red-Team MCP Server.

A Model Context Protocol server that exposes 40+ offensive-security tools
to LLM clients (Cursor, Claude Desktop, Cline, Continue, etc.).

Tools wrapped:
    * Shodan        — internet-wide asset search
    * Nuclei        — templated vulnerability scanner
    * Caido         — modern HTTP proxy
    * Evilginx      — 2FA-bypass phishing proxy
    * Sliver        — open-source C2
    * Havoc         — modern C2
    * Ligolo-ng     — TUN-based pivoting tunnel

Usage is restricted to authorised engagements; see LICENSE.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
