from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.tools.base import ToolResult, ToolSpec
from kestrel_mcp.webui import create_app
from kestrel_mcp.webui.job_runner import JobRunner


async def _echo(arguments):
    return ToolResult(text=f"echo: {arguments['message']}", structured=arguments)


@pytest.fixture
async def setup():
    c = ServiceContainer.in_memory()
    await c.initialise()
    app = create_app(c)
    app.state.tool_specs = {
        "echo": ToolSpec(
            name="echo",
            description="Echo a message.",
            input_schema={"type": "object"},
            handler=_echo,
        )
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield client, app
    await c.dispose()


async def test_list_tools_json(setup):
    client, _ = setup
    r = await client.get("/tools", headers={"accept": "application/json"})
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["tools"][0]["name"] == "echo"


async def test_run_tool_job_completes(setup):
    client, app = setup
    r = await client.post(
        "/tools/run",
        data={"tool_name": "echo", "arguments_json": '{"message": "hello"}'},
        headers={"accept": "application/json"},
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    runner = app.state.tool_runner
    assert isinstance(runner, JobRunner)
    job = await runner.await_done(job_id)
    assert job.status == "done"
    assert job.result_text == "echo: hello"


async def test_run_tool_rejects_bad_json(setup):
    client, _ = setup
    r = await client.post(
        "/tools/run",
        data={"tool_name": "echo", "arguments_json": "not-json"},
        headers={"accept": "application/json"},
    )
    assert r.status_code == 400


async def test_get_missing_job_404(setup):
    client, _ = setup
    r = await client.get("/tools/jobs/nope")
    assert r.status_code == 404
