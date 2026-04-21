"""Unit tests for the scope guard — the single most important security feature."""

from __future__ import annotations

import pytest

from kestrel_mcp.security import AuthorizationError, ScopeGuard


class TestScopeGuard:
    def test_empty_scope_denies_all(self) -> None:
        guard = ScopeGuard([])
        with pytest.raises(AuthorizationError, match="authorized_scope is empty"):
            guard.ensure("example.com", tool_name="x")

    def test_exact_hostname_match(self) -> None:
        guard = ScopeGuard(["api.example.com"])
        guard.ensure("api.example.com", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("app.example.com", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("example.com", tool_name="x")

    def test_wildcard_does_not_match_apex(self) -> None:
        guard = ScopeGuard(["*.example.com"])
        guard.ensure("api.example.com", tool_name="x")
        guard.ensure("a.b.example.com", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("example.com", tool_name="x")

    def test_dot_prefix_matches_both_apex_and_subdomain(self) -> None:
        guard = ScopeGuard([".example.com"])
        guard.ensure("example.com", tool_name="x")
        guard.ensure("api.example.com", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("notexample.com", tool_name="x")

    def test_cidr_match(self) -> None:
        guard = ScopeGuard(["10.0.0.0/16"])
        guard.ensure("10.0.5.12", tool_name="x")
        guard.ensure("10.0.0.1", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("10.1.0.1", tool_name="x")

    def test_url_target_extraction(self) -> None:
        guard = ScopeGuard(["*.example.com"])
        guard.ensure("https://api.example.com/v1/health", tool_name="x")
        guard.ensure("https://api.example.com:8443/", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("https://evil.com/steal", tool_name="x")

    def test_multiple_entries(self) -> None:
        guard = ScopeGuard(["*.example.com", "10.0.0.0/24", "host.test"])
        guard.ensure("sub.example.com", tool_name="x")
        guard.ensure("10.0.0.42", tool_name="x")
        guard.ensure("host.test", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("8.8.8.8", tool_name="x")

    def test_case_insensitive_hostname(self) -> None:
        guard = ScopeGuard(["API.Example.COM"])
        guard.ensure("api.example.com", tool_name="x")
        guard.ensure("API.EXAMPLE.COM", tool_name="x")

    def test_ipv6_literal(self) -> None:
        guard = ScopeGuard(["2001:db8::1"])
        guard.ensure("2001:db8::1", tool_name="x")
        with pytest.raises(AuthorizationError):
            guard.ensure("2001:db8::2", tool_name="x")
