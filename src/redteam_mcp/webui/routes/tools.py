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
