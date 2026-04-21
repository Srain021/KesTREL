---
id: RFC-010b
title: Tool launcher SSE UI
epic: C-WebUI-Tier1
status: open
owner: unassigned
role: fullstack-engineer
blocking_on: [RFC-010a]
budget:
  max_files_touched: 4
  max_new_files: 3
  max_lines_added: 340
  max_minutes_human: 30
  max_tokens_model: 14000
files_to_read:
  - src/redteam_mcp/webui/job_runner.py
  - src/redteam_mcp/webui/routes/tools.py
  - src/redteam_mcp/webui/templating.py
files_will_touch:
  - src/redteam_mcp/webui/routes/tools.py                    # modified
  - src/redteam_mcp/webui/templates/tools/launcher.html.j2   # new
  - src/redteam_mcp/webui/templates/tools/_job_row.html.j2   # new
  - tests/unit/webui/test_tools_sse.py                       # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/webui/test_tools_sse.py -v
rollback_cmd: git checkout -- src\redteam_mcp\webui\routes\tools.py && rmdir /S /Q src\redteam_mcp\webui\templates\tools 2>nul && del tests\unit\webui\test_tools_sse.py 2>nul
skill_id: rfc-010b-tool-launcher-sse-ui
---

# RFC-010b - Tool launcher SSE UI

## Mission

Add the HTML launcher and SSE stream endpoint on top of RFC-010a jobs.

## Context

- RFC-010a provides `JobRunner`, `/tools/run`, and `/tools/jobs/{id}`.
- This RFC keeps JSON behavior for tests and API clients when `Accept: application/json` is set.
- SSE is a simple one-shot stream for now; realtime chunking can move to RFC-E03.

## Non-goals

- No WebSocket.
- No persistent job storage.
- No schema-driven form generation.

## Steps

### Step 1

WRITE src/redteam_mcp/webui/routes/tools.py
```python
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from ...config import Settings, load_settings
from ...core import RequestContext
from ...security import ScopeGuard
from ...tools import load_modules
from ...tools.base import ToolResult, ToolSpec
from ...workflows import load_workflow_specs
from ..deps import get_ctx
from ..job_runner import JobRunner
from ..templating import templates

router = APIRouter()


def _tool_specs(settings: Settings) -> dict[str, ToolSpec]:
    scope_guard = ScopeGuard(settings.security.authorized_scope)
    specs: dict[str, ToolSpec] = {}
    for module in load_modules(settings, scope_guard):
        for spec in module.specs():
            specs[spec.name] = spec
    for spec in load_workflow_specs(settings, scope_guard):
        specs[spec.name] = spec
    return specs


def _get_specs(request: Request) -> dict[str, ToolSpec]:
    injected = getattr(request.app.state, "tool_specs", None)
    if injected is not None:
        return cast("dict[str, ToolSpec]", injected)
    return _tool_specs(load_settings())


def _get_runner(request: Request, specs: dict[str, ToolSpec]) -> JobRunner:
    injected = getattr(request.app.state, "tool_runner", None)
    if isinstance(injected, JobRunner):
        return injected

    async def call_tool(tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = specs.get(tool_name)
        if spec is None:
            return ToolResult.error(f"Unknown tool: {tool_name}")
        return await spec.handler(arguments)

    runner = JobRunner(call_tool)
    request.app.state.tool_runner = runner
    return runner


def _parse_arguments(arguments_json: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid JSON arguments: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(400, "Tool arguments must be a JSON object")
    return cast("dict[str, Any]", parsed)


def _tool_payload(specs: dict[str, ToolSpec]) -> list[dict[str, object]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "dangerous": spec.dangerous,
            "tags": spec.tags,
        }
        for spec in specs.values()
    ]


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def list_tools(request: Request) -> Response:
    specs = _get_specs(request)
    tools = _tool_payload(specs)
    if _wants_json(request):
        return JSONResponse({"count": len(tools), "tools": tools})
    return templates.TemplateResponse(
        request,
        "tools/launcher.html.j2",
        {"active_engagement": None, "jobs": [], "tools": tools},
    )


@router.post("/run")
async def run_tool(
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
    tool_name: Annotated[str, Form()],
    arguments_json: Annotated[str, Form()] = "{}",
) -> Response:
    specs = _get_specs(request)
    if tool_name not in specs:
        raise HTTPException(404, f"Unknown tool: {tool_name}")
    arguments = _parse_arguments(arguments_json)
    runner = _get_runner(request, specs)
    job = await runner.start(tool_name, arguments, ctx)
    if _wants_json(request):
        return JSONResponse(job.as_dict())
    return templates.TemplateResponse(request, "tools/_job_row.html.j2", {"job": job})


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str) -> dict[str, object]:
    runner = _get_runner(request, _get_specs(request))
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(404, f"Unknown job: {job_id}")
    return job.as_dict()


@router.get("/jobs/{job_id}/stream")
async def stream_job(request: Request, job_id: str) -> StreamingResponse:
    runner = _get_runner(request, _get_specs(request))
    if runner.get(job_id) is None:
        raise HTTPException(404, f"Unknown job: {job_id}")
    return StreamingResponse(_sse_events(runner, job_id), media_type="text/event-stream")


async def _sse_events(runner: JobRunner, job_id: str) -> AsyncIterator[str]:
    async for event, data in runner.stream(job_id):
        payload = data.replace("\r", "").replace("\n", "\\n")
        yield f"event: {event}\ndata: {payload}\n\n"
```

### Step 2

WRITE src/redteam_mcp/webui/templates/tools/launcher.html.j2
```html
{% extends "base.html.j2" %}
{% block title %}Tool launcher &middot; kestrel-mcp{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold">Tool launcher</h1>
<p class="text-sm text-slate-500 mb-6">
  Launch one MCP tool as an in-memory Web UI job. Jobs are not persisted across restarts.
</p>

<div class="grid grid-cols-3 gap-6">
  <form hx-post="/tools/run" hx-target="#jobs tbody" hx-swap="beforeend"
        class="col-span-1 bg-white border rounded-xl p-4 text-sm">
    <label class="block mb-3">
      <span class="block text-xs text-slate-500 mb-1">Tool</span>
      <select name="tool_name" required class="w-full border rounded px-2 py-1">
        {% for tool in tools %}
        <option value="{{ tool.name }}">{{ tool.name }}</option>
        {% endfor %}
      </select>
    </label>
    <label class="block mb-3">
      <span class="block text-xs text-slate-500 mb-1">Arguments JSON</span>
      <textarea name="arguments_json" rows="8" class="w-full border rounded px-2 py-1 font-mono text-xs">{}</textarea>
    </label>
    <button type="submit" class="bg-slate-800 text-white px-4 py-1 rounded">Launch</button>
  </form>

  <div class="col-span-2 bg-white border rounded-xl overflow-hidden">
    <table id="jobs" class="w-full text-sm">
      <thead class="bg-slate-50">
        <tr>
          <th class="px-3 py-2 text-left">Job</th>
          <th class="px-3 py-2 text-left">Tool</th>
          <th class="px-3 py-2 text-left">Status</th>
          <th class="px-3 py-2 text-left">Stream</th>
        </tr>
      </thead>
      <tbody>
        {% for job in jobs %}
          {% include "tools/_job_row.html.j2" with context %}
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

### Step 3

WRITE src/redteam_mcp/webui/templates/tools/_job_row.html.j2
```html
<tr id="job-{{ job.id }}" class="border-t">
  <td class="px-3 py-2 font-mono text-xs">{{ job.id }}</td>
  <td class="px-3 py-2">{{ job.tool_name }}</td>
  <td class="px-3 py-2">{{ job.status }}</td>
  <td class="px-3 py-2">
    <a class="text-xs text-blue-700 hover:underline" href="/tools/jobs/{{ job.id }}/stream">
      open SSE
    </a>
  </td>
</tr>
```

### Step 4

WRITE tests/unit/webui/test_tools_sse.py
```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from redteam_mcp.core import ServiceContainer
from redteam_mcp.tools.base import ToolResult, ToolSpec
from redteam_mcp.webui import create_app
from redteam_mcp.webui.job_runner import JobRunner


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
```

## Post-checks

- `GET /tools` renders HTML.
- `POST /tools/run` returns a job row for htmx.
- `GET /tools/jobs/{id}/stream` returns `text/event-stream`.

## Updates to other docs

- Update this RFC status to `done`.
- Update `rfcs/INDEX.md`.
- Update `CHANGELOG.md`.
