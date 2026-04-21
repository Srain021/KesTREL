---
id: RFC-006
title: FastAPI app skeleton (shared with MCP container)
epic: C-WebUI-Tier1
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-002]
budget:
  max_files_touched: 7
  max_new_files: 6
  max_lines_added: 320
  max_minutes_human: 25
  max_tokens_model: 14000
files_to_read:
  - src/kestrel_mcp/core/services.py
  - src/kestrel_mcp/core/context.py
  - src/kestrel_mcp/__main__.py
files_will_touch:
  - src/kestrel_mcp/webui/__init__.py       # new
  - src/kestrel_mcp/webui/app.py            # new
  - src/kestrel_mcp/webui/middleware.py     # new
  - src/kestrel_mcp/webui/deps.py           # new
  - tests/unit/webui/__init__.py            # new
  - tests/unit/webui/test_app_skeleton.py   # new
  - pyproject.toml                          # modified (+fastapi, uvicorn, httpx for tests)
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/webui/test_app_skeleton.py -v
rollback_cmd: |
  git checkout -- pyproject.toml
  rmdir /S /Q src\kestrel_mcp\webui 2>nul
  rmdir /S /Q tests\unit\webui 2>nul
skill_id: rfc-006-fastapi-skeleton
---

# RFC-006 — FastAPI app skeleton

## Mission

用 FastAPI 搭 Web 服务骨架：共享 ServiceContainer、注入 RequestContext、基础健康检查路由。

## Context

- UI_STRATEGY.md 推荐 htmx + FastAPI。
- 与现有 MCP server 共进程可选，首版跑独立进程简化路径。
- 本 RFC **不做 UI**，只做 `/` 返回 JSON `{"ok": true}` + `/api/v1/engagements` 返回列表。下一个 RFC (RFC-007) 才加 Jinja + htmx。

## Non-goals

- 不做模板 / htmx（RFC-007）
- 不做认证（RFC-012）
- 不做 WebSocket（RFC-010 / RFC-E03）
- 不做 Docker（RFC-H02）

## Design

- `create_app(container: ServiceContainer) -> FastAPI`  — factory（便于测试）
- 中间件：每个请求开 `container.open_context()`，把 ctx attach 到 `request.state.ctx`
- 依赖注入：`get_ctx(request) -> RequestContext` 给路由用
- 2 个路由：`GET /` 健康 / `GET /api/v1/engagements`

## Steps

### Step 1 — 加依赖

```
REPLACE pyproject.toml
<<<<<<< SEARCH
    "jinja2>=3.1",
]
=======
    "jinja2>=3.1",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
]
>>>>>>> REPLACE
```

```
RUN .venv\Scripts\python.exe -m uv lock
RUN .venv\Scripts\python.exe -m uv sync --frozen
```

（若 pyproject 没有 cryptography 行，锚点换成项目里当前最后一行依赖；必要时调整 SEARCH。）

### Step 2 — webui 包骨架

```
WRITE src/kestrel_mcp/webui/__init__.py
```
```python
"""Web UI sub-package.

Loaded only when the user runs ``kestrel-mcp web`` or imports
``kestrel_mcp.webui.create_app`` directly. Does NOT couple the MCP
server to FastAPI — keep imports lazy so the MCP-only install stays
lightweight.
"""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]
```

### Step 3 — deps.py

```
WRITE src/kestrel_mcp/webui/deps.py
```
```python
"""FastAPI dependency functions."""

from __future__ import annotations

from fastapi import Depends, Request

from ..core import RequestContext


def get_ctx(request: Request) -> RequestContext:
    ctx = getattr(request.state, "ctx", None)
    if ctx is None:
        raise RuntimeError(
            "RequestContext middleware must be installed; see webui.middleware."
        )
    return ctx
```

### Step 4 — middleware.py

```
WRITE src/kestrel_mcp/webui/middleware.py
```
```python
"""ASGI middleware: attach RequestContext to every request.state."""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..core import ServiceContainer


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Open a fresh RequestContext (no active engagement by default).

    Routes that want an engagement bound must read the ``X-Engagement`` header
    or session cookie and re-open the context themselves (Phase C-Tier-2).
    """

    def __init__(self, app, container: ServiceContainer) -> None:
        super().__init__(app)
        self.container = container

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        async with self.container.open_context() as ctx:
            request.state.ctx = ctx
            return await call_next(request)
```

### Step 5 — app.py

```
WRITE src/kestrel_mcp/webui/app.py
```
```python
"""FastAPI application factory."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from ..core import RequestContext, ServiceContainer
from .deps import get_ctx
from .middleware import RequestContextMiddleware


def create_app(container: ServiceContainer) -> FastAPI:
    app = FastAPI(
        title="kestrel-mcp web",
        version="0.1.0",
        docs_url="/__docs",
        redoc_url=None,
    )

    app.add_middleware(RequestContextMiddleware, container=container)

    @app.get("/", include_in_schema=False)
    async def root():
        return {"ok": True, "service": "kestrel-mcp web"}

    @app.get("/api/v1/engagements")
    async def list_engagements(ctx: RequestContext = Depends(get_ctx)):
        engagements = await ctx.engagement.list()
        return {
            "count": len(engagements),
            "engagements": [
                {"id": str(e.id), "name": e.name, "status": e.status.value}
                for e in engagements
            ],
        }

    return app
```

### Step 6 — 测试

```
WRITE tests/unit/webui/__init__.py
```

```
WRITE tests/unit/webui/test_app_skeleton.py
```
```python
"""App skeleton smoke tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.webui import create_app


@pytest.fixture
async def container():
    c = ServiceContainer.in_memory()
    await c.initialise()
    try:
        yield c
    finally:
        await c.dispose()


@pytest.fixture
async def client(container):
    app = create_app(container)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_root_ok(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_engagements_empty(client):
    r = await client.get("/api/v1/engagements")
    assert r.status_code == 200
    assert r.json() == {"count": 0, "engagements": []}


async def test_engagements_after_seed(client, container):
    await container.engagement.create(
        name="demo", display_name="Demo",
        engagement_type=ent.EngagementType.CTF, client="c",
    )
    r = await client.get("/api/v1/engagements")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["engagements"][0]["name"] == "demo"


async def test_openapi_served(client):
    r = await client.get("/__docs")
    assert r.status_code == 200
```

### Step 7 — verify + full_verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/webui/ -v
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Post-checks

- [ ] `git diff --stat` 只列 `files_will_touch`
- [ ] 4 个新 webui 测试绿
- [ ] full_verify 8/8
- [ ] `src/kestrel_mcp/webui/` 下面没有 template 文件（UI 下一个 RFC 才引入）

## Updates to other docs

- `CHANGELOG.md`: `RFC-006 — FastAPI app skeleton`
- `MASTER_PLAN.md`: Sprint 4 Day 1 打勾

## Notes for executor

- httpx 已经是项目依赖，不需要再加。
- 不要新增 `endpoints.py` / `routes.py` —— 路由就写在 `app.py` 工厂里，后续 RFC 再按需拆分。
- `ASGITransport` 是 httpx 0.28+ 的 API；如果本地 httpx 较旧 `uv sync` 会解决。

## Changelog

- **2026-04-21 初版**
