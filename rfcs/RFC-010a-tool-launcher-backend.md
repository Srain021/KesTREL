---
id: RFC-010a
title: Tool launcher backend jobs
epic: C-WebUI-Tier1
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-008]
budget:
  max_files_touched: 4
  max_new_files: 3
  max_lines_added: 320
  max_minutes_human: 30
  max_tokens_model: 14000
files_to_read:
  - src/redteam_mcp/tools/base.py
  - src/redteam_mcp/tools/__init__.py
  - src/redteam_mcp/webui/routes/__init__.py
files_will_touch:
  - src/redteam_mcp/webui/job_runner.py           # new
  - src/redteam_mcp/webui/routes/tools.py         # new
  - src/redteam_mcp/webui/routes/__init__.py      # modified
  - tests/unit/webui/test_tools_backend.py        # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/webui/test_tools_backend.py -v
rollback_cmd: git checkout -- src\redteam_mcp\webui\routes\__init__.py && del src\redteam_mcp\webui\job_runner.py 2>nul && del src\redteam_mcp\webui\routes\tools.py 2>nul && del tests\unit\webui\test_tools_backend.py 2>nul
skill_id: rfc-010a-tool-launcher-backend
---

# RFC-010a - Tool launcher backend jobs

## Mission

Add a small in-memory Web UI job runner and JSON tool-launch backend.

## Context

- Original RFC-010 was too large and is split into backend (`010a`) and UI/SSE (`010b`).
- This RFC avoids depending on `server.RedTeamMCPServer`; it calls `ToolSpec.handler` through an injected `JobRunner`.
- Jobs are in-memory and serialized with a single semaphore.

## Non-goals

- No SSE endpoint yet.
- No HTML templates yet.
- No persistent queue.

## Steps

### Step 1

WRITE src/redteam_mcp/webui/job_runner.py
```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..core import RequestContext
from ..core.context import bind_context
from ..tools.base import ToolResult

ToolCall = Callable[[str, dict[str, Any]], Awaitable[ToolResult]]


@dataclass
class Job:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    status: str = "pending"
    result_text: str = ""
    structured: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    done: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    events: asyncio.Queue[tuple[str, str]] = field(default_factory=asyncio.Queue, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status,
            "result_text": self.result_text,
            "structured": self.structured,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


class JobRunner:
    def __init__(self, call_tool_handler: ToolCall, *, concurrency: int = 1) -> None:
        self._call_tool_handler = call_tool_handler
        self._semaphore = asyncio.Semaphore(concurrency)
        self.jobs: dict[str, Job] = {}

    async def start(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: RequestContext,
    ) -> Job:
        job = Job(id=uuid4().hex, tool_name=tool_name, arguments=arguments)
        self.jobs[job.id] = job
        asyncio.create_task(self._run(job, ctx))
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    async def await_done(self, job_id: str) -> Job:
        job = self.jobs[job_id]
        await job.done.wait()
        return job

    async def stream(self, job_id: str) -> AsyncIterator[tuple[str, str]]:
        job = self.jobs[job_id]
        if job.done.is_set():
            yield ("done", job.result_text or job.error or "")
            return

        while True:
            event, data = await job.events.get()
            yield (event, data)
            if event in {"done", "error"}:
                return

    async def _run(self, job: Job, ctx: RequestContext) -> None:
        job.status = "running"
        await job.events.put(("status", "running"))
        try:
            async with self._semaphore:
                with bind_context(ctx):
                    result = await self._call_tool_handler(job.tool_name, job.arguments)
            job.result_text = result.text
            job.structured = result.structured
            job.status = "error" if result.is_error else "done"
            if result.is_error:
                job.error = result.text
                await job.events.put(("error", result.text))
            else:
                await job.events.put(("done", result.text))
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = str(exc)
            await job.events.put(("error", str(exc)))
        finally:
            job.done.set()
```

### Step 2

WRITE src/redteam_mcp/webui/routes/tools.py
```python
from __future__ import annotations

import json
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from ...config import Settings, load_settings
from ...core import RequestContext
from ...security import ScopeGuard
from ...tools import load_modules
from ...tools.base import ToolResult, ToolSpec
from ...workflows import load_workflow_specs
from ..deps import get_ctx
from ..job_runner import JobRunner

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


@router.get("")
@router.get("/")
async def list_tools(request: Request) -> dict[str, object]:
    specs = _get_specs(request)
    tools = [
        {
            "name": spec.name,
            "description": spec.description,
            "dangerous": spec.dangerous,
            "tags": spec.tags,
        }
        for spec in specs.values()
    ]
    return {"count": len(tools), "tools": tools}


@router.post("/run")
async def run_tool(
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
    tool_name: Annotated[str, Form()],
    arguments_json: Annotated[str, Form()] = "{}",
) -> dict[str, object]:
    specs = _get_specs(request)
    if tool_name not in specs:
        raise HTTPException(404, f"Unknown tool: {tool_name}")
    arguments = _parse_arguments(arguments_json)
    runner = _get_runner(request, specs)
    job = await runner.start(tool_name, arguments, ctx)
    return job.as_dict()


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str) -> dict[str, object]:
    runner = _get_runner(request, _get_specs(request))
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(404, f"Unknown job: {job_id}")
    return job.as_dict()
```

### Step 3

REPLACE src/redteam_mcp/webui/routes/__init__.py
<<<<<<< SEARCH
from fastapi import APIRouter

from .engagements import router as engagements_router
from .findings import router as findings_router
from .settings import router as settings_router

router = APIRouter()
router.include_router(engagements_router, prefix="/engagements", tags=["engagements"])
router.include_router(
    findings_router,
    prefix="/engagements/{slug}/findings",
    tags=["findings"],
)
router.include_router(settings_router, prefix="/settings", tags=["settings"])
=======
from fastapi import APIRouter

from .engagements import router as engagements_router
from .findings import router as findings_router
from .settings import router as settings_router
from .tools import router as tools_router

router = APIRouter()
router.include_router(engagements_router, prefix="/engagements", tags=["engagements"])
router.include_router(
    findings_router,
    prefix="/engagements/{slug}/findings",
    tags=["findings"],
)
router.include_router(settings_router, prefix="/settings", tags=["settings"])
router.include_router(tools_router, prefix="/tools", tags=["tools"])
>>>>>>> REPLACE

### Step 4

WRITE tests/unit/webui/test_tools_backend.py
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
```

## Post-checks

- `GET /tools` with `Accept: application/json` lists injected specs.
- `POST /tools/run` starts a job and returns a job id.
- `GET /tools/jobs/{id}` returns job status.

## Updates to other docs

- Update this RFC status to `done`.
- Update `rfcs/INDEX.md`.
- Update `CHANGELOG.md`.
