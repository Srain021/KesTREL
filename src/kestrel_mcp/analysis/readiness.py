"""Exploitability readiness scoring.

This module is intentionally local and deterministic. It does not execute
tools, fetch exploit code, or make network requests; it turns existing finding
metadata into an operator-review package.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import cast

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)


class ReadinessRating(str, Enum):
    """Coarse routing state for an operator."""

    PARKED = "parked"
    INVESTIGATE = "investigate"
    READY_TO_VALIDATE = "ready_to_validate"
    OPERATOR_REVIEW = "operator_review"


@dataclass(frozen=True)
class ReadinessSignal:
    name: str
    points: int
    reason: str


@dataclass(frozen=True)
class ReadinessAssessment:
    score: int
    rating: ReadinessRating
    confidence: str
    requires_human_approval: bool
    cves: tuple[str, ...] = ()
    signals: tuple[ReadinessSignal, ...] = ()
    evidence_gaps: tuple[str, ...] = ()
    recommended_next_steps: tuple[str, ...] = ()
    safety_gates: tuple[str, ...] = (
        "Confirm engagement scope and rules of engagement before active validation.",
        "Do not execute exploit, payload, persistence, or credential actions without human approval.",
    )


def assess_exploitability(
    finding: Mapping[str, object] | object,
    *,
    enrichment: Mapping[str, object] | None = None,
    context: Mapping[str, object] | None = None,
) -> ReadinessAssessment:
    """Score a finding for operator readiness.

    The score is not proof that exploitation will succeed. It is a transparent
    prioritization aid that combines severity, evidence, CVE intelligence, and
    exposure context into an operator-facing decision package.
    """

    context = context or {}
    cves = _collect_cves(finding)
    signals: list[ReadinessSignal] = []

    def add(name: str, points: int, reason: str) -> None:
        if points > 0:
            signals.append(ReadinessSignal(name=name, points=points, reason=reason))

    severity = _text(_field(finding, "severity")).lower()
    add("severity", _severity_points(severity), f"Finding severity is {severity or 'unknown'}.")

    cvss = _float(_field(finding, "cvss_score"))
    if cvss is not None:
        add("cvss", min(25, round(cvss * 2.5)), f"CVSS score is {cvss:.1f}.")

    confidence = _text(_field(finding, "confidence")).lower()
    verified = bool(_field(finding, "verified"))
    evidence_count = _evidence_count(finding)
    if verified:
        add("verified", 15, "Finding has been manually or tool-confirmed.")
    elif confidence in {"likely", "confirmed"}:
        add("confidence", 8, f"Finding confidence is {confidence}.")
    if evidence_count:
        add("evidence", min(10, evidence_count * 4), f"{evidence_count} evidence item(s) attached.")

    if cves:
        add("cve_present", 8, f"Finding references {len(cves)} CVE(s).")

    enrichment_records = _enrichment_records(enrichment)
    _add_enrichment_signals(enrichment_records, add)

    if not cves and verified and severity in {"critical", "high"}:
        add(
            "zero_day_hypothesis",
            10,
            "High-impact verified behavior has no CVE; treat as unknown-vulnerability hypothesis.",
        )

    _add_context_signals(context, add)

    score = min(100, sum(signal.points for signal in signals))
    rating = _rating(score)
    gaps = tuple(
        _evidence_gaps(finding, cves, enrichment_records, context, verified, evidence_count)
    )
    steps = tuple(_next_steps(rating, gaps, cves, bool(enrichment_records), not cves and verified))
    approval = rating in {ReadinessRating.READY_TO_VALIDATE, ReadinessRating.OPERATOR_REVIEW}

    return ReadinessAssessment(
        score=score,
        rating=rating,
        confidence=_assessment_confidence(
            score, verified, evidence_count, bool(enrichment_records)
        ),
        requires_human_approval=approval,
        cves=tuple(cves),
        signals=tuple(signals),
        evidence_gaps=gaps,
        recommended_next_steps=steps,
    )


def _field(source: Mapping[str, object] | object, name: str) -> object | None:
    if isinstance(source, Mapping):
        return source.get(name)
    return cast(object | None, getattr(source, name, None))


def _text(value: object | None) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", value)
    return str(enum_value).strip()


def _float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _truthy(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "known", "known_exploited"}
    return bool(value)


def _strings(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _collect_cves(finding: Mapping[str, object] | object) -> list[str]:
    haystack: list[str] = []
    for field_name in ("cve", "cves", "title", "description", "references"):
        haystack.extend(_strings(_field(finding, field_name)))
    found = {match.group(0).upper() for text in haystack for match in _CVE_RE.finditer(text)}
    return sorted(found)


def _evidence_count(finding: Mapping[str, object] | object) -> int:
    explicit = _field(finding, "evidence_count")
    if (count := _float(explicit)) is not None:
        return max(0, int(count))
    evidence = _field(finding, "evidence")
    if isinstance(evidence, Sequence) and not isinstance(evidence, str | bytes | bytearray):
        return len(evidence)
    return 0


def _severity_points(severity: str) -> int:
    return {"critical": 25, "high": 18, "medium": 10, "low": 4, "info": 1}.get(severity, 0)


def _epss_points(probability: float) -> int:
    if probability >= 0.50:
        return 20
    if probability >= 0.10:
        return 12
    if probability >= 0.01:
        return 6
    return 0


def _add_enrichment_signals(
    enrichment_records: list[Mapping[str, object]],
    signal: SignalAdder,
) -> None:
    if any(_truthy(_field(record, "kev_known_exploited")) for record in enrichment_records):
        signal("cisa_kev", 18, "At least one CVE is listed in CISA KEV.")
    if any(_truthy(_field(record, "known_exploited")) for record in enrichment_records):
        signal("known_exploited", 18, "At least one CVE is marked known exploited.")

    epss_probability = max(
        [
            _float(_field(record, "epss_probability")) or _float(_field(record, "epss")) or 0.0
            for record in enrichment_records
        ],
        default=0.0,
    )
    epss_percentile = max(
        [
            _float(_field(record, "epss_percentile")) or _float(_field(record, "percentile")) or 0.0
            for record in enrichment_records
        ],
        default=0.0,
    )
    signal(
        "epss_probability",
        _epss_points(epss_probability),
        f"Max EPSS probability is {epss_probability:.3f}.",
    )
    if epss_percentile >= 0.95:
        signal("epss_percentile", 8, f"Max EPSS percentile is {epss_percentile:.3f}.")


def _add_context_signals(context: Mapping[str, object], signal: SignalAdder) -> None:
    if _truthy(context.get("internet_exposed")):
        signal("internet_exposed", 8, "Target is internet-exposed.")
    if context.get("auth_required") is False:
        signal("no_auth_required", 6, "Observed attack surface does not require authentication.")
    if _text(context.get("privileges_required")).lower() in {"none", "low"}:
        signal("low_privileges_required", 5, "Validation appears to need low or no privileges.")
    if _text(context.get("asset_criticality")).lower() in {"critical", "high"}:
        signal("asset_criticality", 7, "Target asset is business-critical or high value.")


SignalAdder = Callable[[str, int, str], None]


def _enrichment_records(enrichment: Mapping[str, object] | None) -> list[Mapping[str, object]]:
    if not enrichment:
        return []
    items = enrichment.get("items")
    if isinstance(items, Sequence) and not isinstance(items, str | bytes | bytearray):
        return [cast(Mapping[str, object], item) for item in items if isinstance(item, Mapping)]
    records = [
        cast(Mapping[str, object], value)
        for key, value in enrichment.items()
        if isinstance(key, str) and key.upper().startswith("CVE-") and isinstance(value, Mapping)
    ]
    return records or [enrichment]


def _rating(score: int) -> ReadinessRating:
    if score >= 75:
        return ReadinessRating.OPERATOR_REVIEW
    if score >= 55:
        return ReadinessRating.READY_TO_VALIDATE
    if score >= 25:
        return ReadinessRating.INVESTIGATE
    return ReadinessRating.PARKED


def _assessment_confidence(
    score: int, verified: bool, evidence_count: int, has_enrichment: bool
) -> str:
    if verified and evidence_count and (has_enrichment or score >= 75):
        return "high"
    if verified or evidence_count or has_enrichment or score >= 55:
        return "medium"
    return "low"


def _evidence_gaps(
    finding: Mapping[str, object] | object,
    cves: list[str],
    enrichment_records: list[Mapping[str, object]],
    context: Mapping[str, object],
    verified: bool,
    evidence_count: int,
) -> list[str]:
    gaps: list[str] = []
    if not verified:
        gaps.append("manual validation evidence")
    if not evidence_count:
        gaps.append("request/response, tool output, screenshot, or log artifact")
    if cves and not enrichment_records:
        gaps.append("EPSS and CISA KEV enrichment")
    if not cves and not _strings(_field(finding, "cwe")):
        gaps.append("CVE/CWE classification or unknown-vulnerability rationale")
    if not (_field(finding, "cvss_score") or _field(finding, "cvss_vector")):
        gaps.append("CVSS score or vector")
    if not (context.get("service") or context.get("product") or context.get("version")):
        gaps.append("service, product, and version fingerprint")
    return gaps


def _next_steps(
    rating: ReadinessRating,
    gaps: tuple[str, ...],
    cves: list[str],
    has_enrichment: bool,
    zero_day_candidate: bool,
) -> list[str]:
    steps: list[str] = []
    if gaps:
        steps.append(
            "Close evidence gaps before any high-risk action: " + "; ".join(gaps[:3]) + "."
        )
    if cves and not has_enrichment:
        steps.append("Enrich CVEs with EPSS and CISA KEV before prioritizing operator time.")
    if zero_day_candidate:
        steps.append(
            "Open a zero-day hypothesis record with isolated reproduction notes and sanitized evidence."
        )
    if rating is ReadinessRating.OPERATOR_REVIEW:
        steps.append(
            "Prepare an operator fire-control packet for human approval; do not auto-execute."
        )
    elif rating is ReadinessRating.READY_TO_VALIDATE:
        steps.append("Run scoped validation checks and attach evidence before escalation.")
    elif rating is ReadinessRating.INVESTIGATE:
        steps.append(
            "Gather version, reachability, and exploitability evidence before ranking higher."
        )
    else:
        steps.append(
            "Park unless new evidence, exposure, or threat intelligence changes the score."
        )
    return steps
