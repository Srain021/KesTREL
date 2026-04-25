from __future__ import annotations

from kestrel_mcp.config import Settings
from kestrel_mcp.security import ScopeGuard
from kestrel_mcp.tools.readiness_tool import ReadinessModule


def _specs():
    module = ReadinessModule(Settings(), ScopeGuard(["*.example.com"]))
    return {spec.name: spec for spec in module.specs()}


async def test_readiness_tools_exist_and_are_advisory() -> None:
    specs = _specs()
    expected = {
        "exploitability_triage",
        "attack_path_plan",
        "operator_fire_control",
        "zero_day_hypothesis",
        "evidence_pack",
    }
    assert set(specs) == expected
    for spec in specs.values():
        assert not spec.dangerous
        assert {"helper", "audit"} <= set(spec.tags)
        rendered = spec.render_full_description().lower()
        assert (
            "never execute" in rendered
            or "does not execute" in rendered
            or "do not execute" in rendered
        )


async def test_exploitability_triage_returns_operator_review() -> None:
    specs = _specs()
    result = await specs["exploitability_triage"].handler(
        {
            "finding": {
                "title": "Critical RCE CVE-2024-9999",
                "severity": "critical",
                "confidence": "confirmed",
                "cve": ["CVE-2024-9999"],
                "cvss_score": 9.8,
                "verified": True,
                "evidence_count": 2,
            },
            "enrichment": {
                "CVE-2024-9999": {
                    "epss_probability": 0.8,
                    "epss_percentile": 0.99,
                    "kev_known_exploited": True,
                }
            },
            "context": {
                "internet_exposed": True,
                "auth_required": False,
                "service": "https",
            },
        }
    )

    assert not result.is_error
    assert result.structured is not None
    assert result.structured["rating"] == "operator_review"
    assert result.structured["requires_human_approval"] is True


async def test_attack_path_plan_orders_by_score() -> None:
    specs = _specs()
    result = await specs["attack_path_plan"].handler(
        {
            "target": "app.example.com",
            "findings": [
                {"title": "Info leak", "severity": "low", "verified": False},
                {
                    "title": "Critical CVE-2024-9999",
                    "severity": "critical",
                    "verified": True,
                    "evidence_count": 1,
                    "cve": ["CVE-2024-9999"],
                },
            ],
            "context": {"internet_exposed": True, "service": "https"},
        }
    )

    assert result.structured is not None
    steps = result.structured["steps"]
    assert steps[0]["score"] >= steps[1]["score"]
    assert result.structured["approval_required_before_execution"] is True


async def test_fire_control_packet_requires_human_approval() -> None:
    specs = _specs()
    result = await specs["operator_fire_control"].handler(
        {
            "proposed_action": "Run scoped validation check",
            "target": "app.example.com",
            "rationale": "High-confidence finding needs human-approved validation.",
            "risk_level": "high",
            "evidence_refs": ["finding://1"],
        }
    )

    assert result.structured is not None
    assert result.structured["approval_required"] is True
    assert result.structured["approved"] is False
    assert result.structured["next_state"] == "wait_for_human_approval"


async def test_zero_day_hypothesis_and_evidence_pack_are_structured() -> None:
    specs = _specs()
    hypothesis = await specs["zero_day_hypothesis"].handler(
        {
            "title": "Unauthenticated crash",
            "target": "app.example.com",
            "observed_behavior": "A crafted request causes repeatable 500s.",
        }
    )
    pack = await specs["evidence_pack"].handler(
        {
            "title": "Operator handoff",
            "scope": "*.example.com",
            "findings": [{"title": "Unauth crash", "severity": "high"}],
            "tool_outputs": [{"tool": "httpx_probe", "count": 1}],
        }
    )

    assert hypothesis.structured is not None
    assert "Do not generate exploit code or payloads." in hypothesis.structured["do_not"]
    assert pack.structured is not None
    assert pack.structured["findings_count"] == 1
    assert pack.structured["redaction_level"] == "sanitized"
