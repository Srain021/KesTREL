"""Small deterministic planner for HARNESS MVP."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from ..domain import entities as ent
from ..tools.base import ToolSpec


@dataclass(frozen=True)
class HarnessPolicy:
    local_result_item_limit: int = 20
    broad_result_item_limit: int = 50
    max_failed_steps_before_strong: int = 2


@dataclass(frozen=True)
class PlannedStep:
    tool_name: str
    arguments: dict[str, object]
    risk_level: str
    recommended_model_tier: str
    reason: str

    @property
    def requires_confirmation(self) -> bool:
        return self.risk_level == "high"


class HarnessPlanner:
    def __init__(
        self,
        specs: dict[str, ToolSpec],
        *,
        policy: HarnessPolicy | None = None,
    ) -> None:
        self._specs = specs
        self._policy = policy or HarnessPolicy()

    def next_step(
        self,
        session: ent.HarnessSession,
        steps: list[ent.HarnessStep],
    ) -> PlannedStep | None:
        open_step = _first_open_step(steps)
        if open_step is not None:
            return None

        target = session.target or infer_target(session.goal)
        if not target:
            return None

        attempted = {step.tool_name for step in steps}
        failed_count = sum(1 for step in steps if step.status == ent.HarnessStepStatus.FAILED)
        target_type = classify_target(target)

        if failed_count and "target_list" in self._specs and "target_list" not in attempted:
            tier = "strong" if failed_count >= self._policy.max_failed_steps_before_strong else "standard"
            return self._plan(
                "target_list",
                {},
                "low",
                "Previous HARNESS step failed; inspect persisted targets before retrying.",
                recommended_model_tier=tier,
            )

        if "scope_check" not in attempted and "scope_check" in self._specs:
            return self._plan(
                "scope_check",
                {"target": target},
                "low",
                "Verify scope first.",
                recommended_model_tier="local",
            )

        if "target_add" not in attempted and "target_add" in self._specs:
            return self._plan(
                "target_add",
                {
                    "kind": target_kind_for_add(target_type),
                    "value": target,
                    "discovered_by_tool": "harness",
                },
                "low",
                "Persist the operator-provided target before scanning.",
                recommended_model_tier="local",
            )

        if _has_large_result(steps, self._policy) and "target_list" not in attempted and "target_list" in self._specs:
            return self._plan(
                "target_list",
                {},
                "low",
                "Recent results exceed the local-model fan-out budget; review targets and choose a narrower subset.",
                recommended_model_tier="standard",
            )

        if target_type == "domain" and "subfinder_enum" not in attempted and "subfinder_enum" in self._specs:
            return self._plan(
                "subfinder_enum",
                {"domain": strip_url(target), "silent": True},
                "medium",
                "Run one passive domain enumeration step.",
                recommended_model_tier="local",
            )

        if target_type == "ip" and "nmap_scan" not in attempted and "nmap_scan" in self._specs:
            return self._plan(
                "nmap_scan",
                {"targets": [target], "ports": "1-1024", "timing": 3},
                "medium",
                "Run one bounded TCP discovery step.",
                recommended_model_tier="local",
            )

        if target_type in {"domain", "url", "ip"} and "httpx_probe" not in attempted and "httpx_probe" in self._specs:
            return self._plan(
                "httpx_probe",
                {"targets": [target], "tech_detect": True, "status_code": True, "title": True},
                "medium",
                "Confirm one live HTTP surface before vulnerability scanning.",
                recommended_model_tier="local",
            )

        if "nuclei_scan" not in attempted and "nuclei_scan" in self._specs:
            scan_target = target if target.startswith(("http://", "https://")) else target
            return self._plan(
                "nuclei_scan",
                {"targets": [scan_target], "severity": ["critical", "high"]},
                "medium",
                "Run a narrow high-signal vulnerability baseline; standard tier should interpret findings.",
                recommended_model_tier="standard",
            )

        return None

    def _plan(
        self,
        tool_name: str,
        arguments: dict[str, object],
        risk_level: str,
        reason: str,
        *,
        recommended_model_tier: str | None = None,
    ) -> PlannedStep:
        spec = self._specs[tool_name]
        if _is_high_risk(spec):
            risk_level = "high"
        tier = recommended_model_tier or spec.preferred_model_tier
        if risk_level == "high":
            tier = "strong"
        return PlannedStep(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            recommended_model_tier=tier,
            reason=reason,
        )


def _first_open_step(steps: list[ent.HarnessStep]) -> ent.HarnessStep | None:
    for step in steps:
        if step.status in {
            ent.HarnessStepStatus.PENDING,
            ent.HarnessStepStatus.RUNNING,
            ent.HarnessStepStatus.NEEDS_CONFIRMATION,
        }:
            return step
    return None


def _has_large_result(steps: list[ent.HarnessStep], policy: HarnessPolicy) -> bool:
    for step in reversed(steps):
        if step.status != ent.HarnessStepStatus.DONE or not step.result_summary:
            continue
        count = _result_count(step.result_summary)
        if count is None:
            return False
        if "findings_count=" in step.result_summary:
            return count > policy.local_result_item_limit
        return count > policy.broad_result_item_limit
    return None


def _result_count(summary: str) -> int | None:
    for key in ("findings_count", "count", "hosts", "probes", "results", "subdomains"):
        match = re.search(rf"\b{key}=(\d+)\b", summary)
        if match:
            return int(match.group(1))
    return False
    return False


def infer_target(goal: str) -> str | None:
    match = re.search(r"https?://[^\s,]+", goal)
    if match:
        return match.group(0).rstrip(".")
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", goal)
    if match:
        return match.group(0)
    match = re.search(r"\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", goal)
    if match:
        return match.group(0).rstrip(".")
    return None


def classify_target(target: str) -> str:
    if target.startswith(("http://", "https://")):
        return "url"
    try:
        ipaddress.ip_address(target)
        return "ip"
    except ValueError:
        return "domain"


def target_kind_for_add(target_type: str) -> str:
    if target_type == "url":
        return "url"
    if target_type == "ip":
        return "ipv4"
    return "domain"


def strip_url(target: str) -> str:
    parsed = urlparse(target)
    return parsed.netloc or target


def _is_high_risk(spec: ToolSpec) -> bool:
    tags = set(spec.tags)
    if tags & {"c2", "exploit", "post-ex", "credentials", "phish"}:
        return True
    return spec.name.startswith(("sliver_", "evilginx_", "havoc_", "impacket_"))
