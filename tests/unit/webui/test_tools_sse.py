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


async def test_launcher_page_renders(setup):
    client, _ = setup
    r = await client.get("/tools")
    assert r.status_code == 200
    assert "Tool launcher" in r.text
    assert "echo" in r.text


async def test_run_returns_job_row(setup):
    client, _ = setup
    r = await client.post(
        "/tools/run",
        data={"tool_name": "echo", "arguments_json": '{"message": "hello"}'},
    )
    assert r.status_code == 200
    assert "open SSE" in r.text
    assert "echo" in r.text


async def test_stream_done_event(setup):
    client, app = setup
    r = await client.post(
        "/tools/run",
        data={"tool_name": "echo", "arguments_json": '{"message": "stream"}'},
        headers={"accept": "application/json"},
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    runner = app.state.tool_runner
    assert isinstance(runner, JobRunner)
    await runner.await_done(job_id)

    stream = await client.get(f"/tools/jobs/{job_id}/stream")
    assert stream.status_code == 200
    assert "event: done" in stream.text
    assert "echo: stream" in stream.text
