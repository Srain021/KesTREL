"""Authorization & scope enforcement.

A target is a hostname, IP, or URL supplied by the LLM. Before any tool
acts on a target we check it against :class:`~redteam_mcp.config.SecuritySettings`
``authorized_scope``. This is a BEST-EFFORT safeguard — the user is still
responsible for only adding in-scope entries.

Supported scope grammar:

    exact         host.example.com
    wildcard      *.example.com          (matches one or more labels, NOT the bare domain)
    bare+wildcard .example.com           (matches both the apex and any subdomain)
    ipv4          10.0.0.1
    cidr          10.0.0.0/16
    url           https://example.com    (hostname is extracted)
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


class AuthorizationError(Exception):
    """Raised when a tool tries to act on an out-of-scope target."""


@dataclass(frozen=True)
class Scope:
    """An individual, pre-parsed scope entry."""

    raw: str

    def matches(self, target: str) -> bool:
        host = _extract_host(target)
        if host is None:
            return False

        if _is_ip(host):
            return self._matches_ip(host)
        return self._matches_hostname(host.lower())

    def _matches_ip(self, ip: str) -> bool:
        entry = self.raw.strip()
        try:
            if "/" in entry:
                net = ipaddress.ip_network(entry, strict=False)
                return ipaddress.ip_address(ip) in net
            return ipaddress.ip_address(entry) == ipaddress.ip_address(ip)
        except ValueError:
            return False

    def _matches_hostname(self, host: str) -> bool:
        entry = self.raw.strip().lower()
        if entry.startswith("."):
            base = entry[1:]
            return host == base or host.endswith("." + base)
        if entry.startswith("*."):
            suffix = entry[2:]
            return host.endswith("." + suffix)
        return host == entry


def _extract_host(target: str) -> str | None:
    target = target.strip()
    if not target:
        return None
    if "://" in target:
        parsed = urlparse(target)
        host = parsed.hostname
        return host or None
    if "/" in target and not _is_ip_or_cidr(target):
        return target.split("/", 1)[0] or None
    if ":" in target and target.count(":") == 1 and not _is_ipv6(target):
        return target.split(":", 1)[0] or None
    return target


_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _is_ipv6(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv6Address)
    except ValueError:
        return False


def _is_ip_or_cidr(value: str) -> bool:
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        return False


class ScopeGuard:
    """Enforces the engagement scope.

    Created once per process and shared by all tools.
    """

    def __init__(self, entries: Iterable[str]) -> None:
        self._scopes: list[Scope] = [Scope(e) for e in entries if e.strip()]

    @property
    def empty(self) -> bool:
        return not self._scopes

    def matches(self, target: str) -> bool:
        return any(s.matches(target) for s in self._scopes)

    def ensure(self, target: str, *, tool_name: str) -> None:
        """Raise ``AuthorizationError`` if the target is out of scope.

        If the scope list is empty we DENY by default — this forces the
        operator to explicitly authorise every engagement.
        """

        if self.empty:
            raise AuthorizationError(
                f"Tool '{tool_name}' refused: authorized_scope is empty. "
                "Set REDTEAM_MCP_AUTHORIZED_SCOPE or config.security.authorized_scope "
                "to the engagement's in-scope targets before running offensive tools."
            )
        if not self.matches(target):
            raise AuthorizationError(
                f"Tool '{tool_name}' refused: target '{target}' is NOT within the "
                "authorized engagement scope. Refusing to proceed."
            )


__all__ = ["AuthorizationError", "Scope", "ScopeGuard"]
