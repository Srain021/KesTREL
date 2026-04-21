"""Tests for Sprint 3.2 — tools auto-writing domain entities.

Specifically:

* ``NucleiModule._persist_findings`` creates Target + Finding rows from
  a JSONL batch when a RequestContext has an active engagement.
* ``ShodanModule._ingest_search_hits`` creates Target rows for in-scope IPs.
* Without an active engagement, both are no-ops (legacy mode).
"""

from __future__ import annotations

import pytest

from kestrel_mcp.config import Settings
from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.nuclei_tool import (
    NucleiModule,
    _best_target_for,
    _coerce_cvss,
    _nuclei_severity_to_domain,
)
from kestrel_mcp.tools.shodan_tool import ShodanModule


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


@pytest.fixture
def nuclei_mod():
    return NucleiModule(Settings(), ScopeGuard([]))


@pytest.fixture
def shodan_mod():
    return ShodanModule(Settings(), ScopeGuard([]))


# --- pure translation helpers ---


def test_nuclei_severity_maps():
    assert _nuclei_severity_to_domain("critical") == ent.FindingSeverity.CRITICAL
    assert _nuclei_severity_to_domain("HIGH") == ent.FindingSeverity.HIGH
    assert _nuclei_severity_to_domain("garbage") == ent.FindingSeverity.INFO
    assert _nuclei_severity_to_domain(None) == ent.FindingSeverity.INFO


def test_cvss_coercion():
    assert _coerce_cvss(7.5) == 7.5
    assert _coerce_cvss("7.5") == 7.5
    assert _coerce_cvss(11.0) == 10.0  # clamped
    assert _coerce_cvss(-1) == 0.0
    assert _coerce_cvss(None) is None
    assert _coerce_cvss("not-a-number") is None


# --- Nuclei persistence ---


async def test_nuclei_persist_findings_noop_without_engagement(container, nuclei_mod):
    async with container.open_context():  # no engagement
        persisted = await nuclei_mod._persist_findings(
            ["http://x.lab/"],
            [_fake_finding("SQL injection", "critical")],
        )
    assert persisted == 0


async def test_nuclei_persist_findings_creates_target_and_finding(container, nuclei_mod):
    e = await container.engagement.create(
        name="n",
        display_name="n",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    async with container.open_context(engagement_id=e.id):
        persisted = await nuclei_mod._persist_findings(
            ["http://api.lab.test/"],
            [
                _fake_finding(
                    "SQL injection in /login", "critical", cwe="CWE-89", cve="CVE-2024-1234"
                ),
                _fake_finding("Reflected XSS", "medium"),
            ],
        )
    assert persisted == 2

    # Verify DB contains both
    async with container.open_context(engagement_id=e.id):
        findings = await container.finding.list_for_engagement(e.id)
        assert len(findings) == 2
        titles = sorted(f.title for f in findings)
        assert titles == ["Reflected XSS", "SQL injection in /login"]
        critical = [f for f in findings if f.severity == ent.FindingSeverity.CRITICAL][0]
        assert critical.cwe == ["CWE-89"]
        assert critical.cve == ["CVE-2024-1234"]

        # Target created automatically
        targets = await container.target.list_for_engagement(e.id)
        assert len(targets) == 1
        assert targets[0].value == "http://api.lab.test/"
        assert targets[0].discovered_by_tool == "nuclei_scan"


async def test_nuclei_persist_picks_best_target(container, nuclei_mod):
    e = await container.engagement.create(
        name="n2",
        display_name="n2",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    async with container.open_context(engagement_id=e.id):
        # Two target URLs; one is a prefix of matched-at
        persisted = await nuclei_mod._persist_findings(
            ["http://a.lab/", "http://b.lab/"],
            [_fake_finding("x", "low", matched_at="http://b.lab/login")],
        )
    assert persisted == 1

    async with container.open_context(engagement_id=e.id):
        findings = await container.finding.list_for_engagement(e.id)
        targets = await container.target.list_for_engagement(e.id)
        assert len(findings) == 1
        # Finding must link to b.lab target, not a.lab
        tgt_map = {t.id: t for t in targets}
        assert tgt_map[findings[0].target_id].value == "http://b.lab/"


def test_best_target_for_prefix():
    class DummyT:
        pass

    ents = {
        "http://a.lab/": DummyT(),
        "http://b.lab/": DummyT(),
    }
    chosen = _best_target_for("http://b.lab/admin", ["http://a.lab/", "http://b.lab/"], ents)
    assert chosen is ents["http://b.lab/"]


# --- Shodan ingestion ---


async def test_shodan_ingest_noop_without_scope(container, shodan_mod):
    e = await container.engagement.create(
        name="s",
        display_name="s",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    # scope empty → should NOT ingest
    async with container.open_context(engagement_id=e.id):
        added = await shodan_mod._ingest_search_hits([{"ip": "1.2.3.4"}])
    assert added == 0


async def test_shodan_ingest_respects_scope(container, shodan_mod):
    e = await container.engagement.create(
        name="s2",
        display_name="s2",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    await container.scope.add_entry(e.id, "10.0.0.0/8")

    async with container.open_context(engagement_id=e.id):
        added = await shodan_mod._ingest_search_hits(
            [
                {"ip": "10.0.0.5"},  # in scope
                {"ip": "10.1.2.3"},  # in scope
                {"ip": "8.8.8.8"},  # OUT of scope
                {"ip": None},  # skip
                {},  # skip
            ]
        )
    assert added == 2


async def test_shodan_enrich_target(container, shodan_mod):
    e = await container.engagement.create(
        name="s3",
        display_name="s3",
        engagement_type=ent.EngagementType.CTF,
        client="c",
    )
    await container.scope.add_entry(e.id, "10.0.0.0/8")

    async with container.open_context(engagement_id=e.id):
        # First ingest a target
        await shodan_mod._ingest_search_hits([{"ip": "10.0.0.5"}])
        # Then call the enrichment with host summary
        ok = await shodan_mod._enrich_target_from_host(
            "10.0.0.5",
            {
                "ports": [22, 80],
                "hostnames": ["a.lab"],
                "org": "Example",
                "country": "US",
                "vulns": [],
            },
        )
    assert ok is True

    async with container.open_context(engagement_id=e.id):
        targets = await container.target.list_for_engagement(e.id)
        assert len(targets) == 1
        t = targets[0]
        assert t.open_ports == [22, 80]
        assert t.hostnames == ["a.lab"]
        assert t.organization == "Example"
        assert t.country == "US"


# --- helpers ---


def _fake_finding(
    name: str,
    severity: str,
    *,
    cwe: str | None = None,
    cve: str | None = None,
    matched_at: str | None = None,
) -> dict:
    info: dict = {"name": name, "severity": severity, "description": f"desc of {name}"}
    classification: dict = {}
    if cwe:
        classification["cwe-id"] = cwe
    if cve:
        classification["cve-id"] = cve
    if classification:
        info["classification"] = classification
    return {
        "template-id": "test-template",
        "info": info,
        "matched-at": matched_at or "http://api.lab.test/",
    }
