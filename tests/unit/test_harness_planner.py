from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from kestrel_mcp.domain import entities as ent
from kestrel_mcp.harness.planner import HarnessPlanner
from kestrel_mcp.tools.base import ToolResult, ToolSpec


async def _handler(_args):
    return ToolResult(text="ok")


def _spec(name: str, *, tags: list[str] | None = None) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} helper.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_handler,
        tags=tags or [],
        preferred_model_tier="local",
    )


def _session(target: str) -> ent.HarnessSession:
    now = datetime.now(timezone.utc)
    return ent.HarnessSession(
        id=uuid4(),
        engagement_id=None,
        goal=f"Recon {target}",
        target=target,
        mode="recon",
        model_tier="local",
        state_summary="",
        created_at=now,
        updated_at=now,
    )


def _done(session_id, ordinal: int, tool_name: str) -> ent.HarnessStep:
    now = datetime.now(timezone.utc)
    return ent.HarnessStep(
        id=uuid4(),
        session_id=session_id,
        ordinal=ordinal,
        tool_name=tool_name,
        arguments={},
        status=ent.HarnessStepStatus.DONE,
        risk_level="low",
        recommended_model_tier="local",
        reason="done",
        created_at=now,
        updated_at=now,
    )


def _done_with_summary(
    session_id,
    ordinal: int,
    tool_name: str,
    summary: str,
) -> ent.HarnessStep:
    step = _done(session_id, ordinal, tool_name)
    step.result_summary = summary
    return step


def test_new_target_starts_with_scope_check() -> None:
    planner = HarnessPlanner({"scope_check": _spec("scope_check")})
    session = _session("example.com")

    step = planner.next_step(session, [])

    assert step is not None
    assert step.tool_name == "scope_check"


def test_domain_url_and_ip_choose_correct_recon_step_after_setup() -> None:
    specs = {
        name: _spec(name)
        for name in ["scope_check", "target_add", "subfinder_enum", "httpx_probe", "nmap_scan"]
    }
    planner = HarnessPlanner(specs)

    domain = _session("example.com")
    domain_step = planner.next_step(
        domain,
        [_done(domain.id, 1, "scope_check"), _done(domain.id, 2, "target_add")],
    )

    url = _session("https://app.example.com")
    url_step = planner.next_step(
        url,
        [_done(url.id, 1, "scope_check"), _done(url.id, 2, "target_add")],
    )

    ip = _session("192.0.2.10")
    ip_step = planner.next_step(
        ip,
        [_done(ip.id, 1, "scope_check"), _done(ip.id, 2, "target_add")],
    )

    assert domain_step is not None
    assert domain_step.tool_name == "subfinder_enum"
    assert url_step is not None
    assert url_step.tool_name == "httpx_probe"
    assert ip_step is not None
    assert ip_step.tool_name == "nmap_scan"


def test_large_result_switches_to_scope_narrowing_step() -> None:
    specs = {
        name: _spec(name)
        for name in ["scope_check", "target_add", "subfinder_enum", "httpx_probe", "target_list"]
    }
    planner = HarnessPlanner(specs)
    session = _session("example.com")

    step = planner.next_step(
        session,
        [
            _done(session.id, 1, "scope_check"),
            _done(session.id, 2, "target_add"),
            _done_with_summary(session.id, 3, "subfinder_enum", "found subdomains count=75"),
        ],
    )

    assert step is not None
    assert step.tool_name == "target_list"
    assert "narrower subset" in step.reason
