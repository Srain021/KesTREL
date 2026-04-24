from __future__ import annotations

import pytest

from kestrel_mcp.domain import entities as ent
from kestrel_mcp.domain.services import HarnessService

pytestmark = pytest.mark.asyncio


async def test_harness_service_persists_session_steps_and_state(sm) -> None:
    service = HarnessService(sm)

    session = await service.create_session(
        goal="Recon example.com",
        target="example.com",
        engagement_id=None,
        mode="recon",
        model_tier="local",
    )
    step = await service.add_step(
        session_id=session.id,
        tool_name="scope_check",
        arguments={"target": "example.com"},
        status=ent.HarnessStepStatus.PENDING,
        risk_level="low",
        recommended_model_tier="local",
        reason="Check scope first.",
    )
    await service.update_step(
        step.id,
        status=ent.HarnessStepStatus.DONE,
        result_summary="IN SCOPE: example.com",
    )
    await service.update_session(session.id, state_summary="Scope checked.")

    payload = await service.get_state_payload(session.id)

    assert payload is not None
    assert payload["session"]["state_summary"] == "Scope checked."
    assert payload["steps"][0]["tool_name"] == "scope_check"
    assert payload["steps"][0]["status"] == "done"
