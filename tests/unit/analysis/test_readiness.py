from __future__ import annotations

from uuid import uuid4

from kestrel_mcp.analysis.readiness import ReadinessRating, assess_exploitability
from kestrel_mcp.domain import entities as ent


def test_cve_with_kev_and_high_epss_requires_operator_review() -> None:
    assessment = assess_exploitability(
        {
            "title": "Critical RCE CVE-2024-9999",
            "severity": "critical",
            "confidence": "confirmed",
            "cve": ["CVE-2024-9999"],
            "cvss_score": 9.8,
            "verified": True,
            "evidence_count": 2,
        },
        enrichment={
            "CVE-2024-9999": {
                "epss_probability": 0.72,
                "epss_percentile": 0.99,
                "kev_known_exploited": True,
            }
        },
        context={
            "internet_exposed": True,
            "auth_required": False,
            "privileges_required": "none",
            "asset_criticality": "critical",
            "service": "https",
            "product": "demo",
            "version": "1.2.3",
        },
    )

    assert assessment.rating is ReadinessRating.OPERATOR_REVIEW
    assert assessment.score >= 90
    assert assessment.requires_human_approval is True
    assert "CVE-2024-9999" in assessment.cves
    assert any(signal.name == "cisa_kev" for signal in assessment.signals)
    assert any("fire-control packet" in step for step in assessment.recommended_next_steps)


def test_unverified_medium_finding_stays_investigation_only() -> None:
    assessment = assess_exploitability(
        {
            "title": "Directory listing exposed",
            "severity": "medium",
            "confidence": "suspected",
            "verified": False,
            "evidence": [],
        }
    )

    assert assessment.rating in {ReadinessRating.PARKED, ReadinessRating.INVESTIGATE}
    assert assessment.requires_human_approval is False
    assert "manual validation evidence" in assessment.evidence_gaps
    assert "service, product, and version fingerprint" in assessment.evidence_gaps


def test_verified_high_without_cve_becomes_zero_day_hypothesis_candidate() -> None:
    assessment = assess_exploitability(
        {
            "title": "Unauthenticated crash on crafted request",
            "severity": "high",
            "verified": True,
            "evidence_count": 1,
            "description": "No public CVE found during triage.",
        },
        context={"internet_exposed": True, "auth_required": False, "service": "https"},
    )

    assert any(signal.name == "zero_day_hypothesis" for signal in assessment.signals)
    assert any("zero-day hypothesis" in step for step in assessment.recommended_next_steps)
    assert "CVE/CWE classification or unknown-vulnerability rationale" in assessment.evidence_gaps


def test_domain_finding_enum_values_normalize() -> None:
    finding = ent.Finding(
        engagement_id=uuid4(),
        target_id=uuid4(),
        title="Apache example CVE-2024-12345",
        severity=ent.FindingSeverity.HIGH,
        confidence=ent.Confidence.LIKELY,
        cve=["CVE-2024-12345"],
        cvss_score=8.1,
        discovered_by_tool="nuclei_scan",
        verified=False,
    )

    assessment = assess_exploitability(finding, context={"product": "apache", "version": "2.4"})

    assert assessment.score >= 30
    assert assessment.cves == ("CVE-2024-12345",)
    assert any(signal.name == "severity" for signal in assessment.signals)
