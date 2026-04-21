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
