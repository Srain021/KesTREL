---
id: RFC-010
title: Tool launcher + SSE live stdout stream
epic: C-WebUI-Tier1
status: abandoned
owner: agent
role: fullstack-engineer
blocking_on: [RFC-008]
budget:
  max_files_touched: 6
  max_new_files: 5
  max_lines_added: 400
  max_minutes_human: 35
  max_tokens_model: 18000
files_to_read:
  - src/kestrel_mcp/tools/base.py
  - src/kestrel_mcp/server.py
  - src/kestrel_mcp/core/services.py
files_will_touch:
  - src/kestrel_mcp/webui/routes/tools.py                  # new
  - src/kestrel_mcp/webui/routes/__init__.py               # modified
  - src/kestrel_mcp/webui/templates/tools/launcher.html.j2 # new
  - src/kestrel_mcp/webui/templates/tools/_job_row.html.j2 # new
  - src/kestrel_mcp/webui/job_runner.py                    # new (async queue + SSE)
  - tests/unit/webui/test_tools_routes.py                  # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/webui/test_tools_routes.py -v
rollback_cmd: git checkout -- . && rmdir /S /Q src\kestrel_mcp\webui\templates\tools 2>nul
skill_id: rfc-010-tool-launcher
---

# RFC-010 — Tool launcher + SSE

## Mission

`/tools` 页：列 MCP tools（从 server registry），表单提交触发执行，stdout 实时流回浏览器。

## Context

- 关键用户故事：非命令行用户想跑 `nuclei_scan` 看进度条（即「像 Actions workflow 一样」）。
- SSE 足够，不上 WebSocket（单向推）。
- 每个 job 有个 UUID；浏览器订阅 `/tools/jobs/{id}/stream`。

## Non-goals

- 不做 job 持久化（进程重启就丢；下个 RFC 做持久化）
- 不做队列（直接 asyncio.Task）
- 不做作 tool schema 校验 UI（Tier 2）

## Design

```
class JobRunner:
    async def start(tool_name, arguments, ctx) -> job_id
    async def stream(job_id) -> AsyncIterator[event]  # yields ServerSentEvent
    def status(job_id) -> JobStatus
```

routes：
| method | path | 功能 |
|--------|------|-----|
| GET | /tools | launcher 页（列 tool + launch 表单）|
| POST | /tools/run | 触发 job → 返回 HTMX 把 `_job_row` append 到列表 |
| GET | /tools/jobs/{id}/stream | SSE stream of stdout chunks |
| GET | /tools/jobs/{id} | job 详情（结构化 JSON 或 HTML）|

SSE event types: `stdout`、`stderr`、`done{exit_code}`、`error{message}`。

## Key snippets

```python
# job_runner.py
from fastapi import Request
from fastapi.responses import EventSourceResponse  # or plain StreamingResponse
import asyncio, uuid
from dataclasses import dataclass, field

@dataclass
class Job:
    id: str
    tool_name: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    status: str = "pending"   # pending | running | done | error
    exit_code: int | None = None

class JobRunner:
    def __init__(self): self.jobs: dict[str, Job] = {}

    async def start(self, server, ctx, tool_name, args):
        job = Job(id=uuid.uuid4().hex, tool_name=tool_name); self.jobs[job.id] = job
        async def _run():
            job.status = "running"
            try:
                spec = server._specs[tool_name]
                # Broadcast chunks:
                async for chunk in _execute_with_streaming(spec, args, ctx):
                    await job.queue.put(("stdout", chunk))
                job.status = "done"; job.exit_code = 0
            except Exception as exc:
                await job.queue.put(("error", str(exc))); job.status = "error"
            finally:
                await job.queue.put(("done", None))
        asyncio.create_task(_run())
        return job.id

    async def stream(self, job_id):
        job = self.jobs.get(job_id)
        while True:
            kind, data = await job.queue.get()
            yield {"event": kind, "data": data if data is not None else ""}
            if kind == "done":
                return
```

**注意**：`_execute_with_streaming` 不是标准 ToolSpec 接口 — 本 RFC 顺便扩展 ToolSpec 加可选 `streaming_handler`。**或者** 简化：先不做实时流，job 跑完一次返 stdout（用 `spec.handler(args)`）。

**推荐简化路径**（本 RFC 先做）：

- 不扩 ToolSpec。`_run()` 直接 `await spec.handler(args)`，拿 `ToolResult`。
- SSE 只推 1 个 `done` 事件带完整 text。
- 未来 RFC-E03 加 realtime 时再真正流式。

## Steps（摘要）

1. 写 `job_runner.py`（简化版：无流、只有 `start/status/await_done`）
2. `routes/tools.py`（launcher 表单 + list tools from `server._specs` or from an injected `list_tools()`）
3. templates
4. 3-5 个测试（触发 job → 等完成 → 断言 status=done）

## Notes for executor

- 最安全的方案：让 `JobRunner` 吃一个 `call_tool_handler: Callable[[str, dict], Awaitable[ToolResult]]`，而不是直接拿 server 实例。这样 webui 不依赖 MCP server 类结构，单测里 mock 一下就行。
- UI 上「launch」按钮 disabled 要 show spinner（Alpine.js `x-data` + `x-bind:disabled`）。
- **重要**：默认所有 job 串行（单 Semaphore concurrency=1）避免把机器打爆；可配置。

## verify_cmd

见 front-matter。

## Changelog

- **2026-04-21 初版（骨架）**
