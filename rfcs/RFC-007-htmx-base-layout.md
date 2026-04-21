---
id: RFC-007
title: htmx + Tailwind base layout + nav
epic: C-WebUI-Tier1
status: open
owner: unassigned
role: frontend-engineer
blocking_on: [RFC-006]
budget:
  max_files_touched: 7
  max_new_files: 6
  max_lines_added: 260
  max_minutes_human: 20
  max_tokens_model: 12000
files_to_read:
  - src/redteam_mcp/webui/app.py
files_will_touch:
  - src/redteam_mcp/webui/templates/base.html.j2      # new
  - src/redteam_mcp/webui/templates/_nav.html.j2      # new
  - src/redteam_mcp/webui/templates/dashboard.html.j2 # new
  - src/redteam_mcp/webui/templating.py               # new
  - src/redteam_mcp/webui/app.py                      # modified (mount templates + "/" serves HTML)
  - tests/unit/webui/test_html_smoke.py               # new
  - pyproject.toml                                    # modified (+jinja2 if missing)
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/webui/test_html_smoke.py -v
rollback_cmd: git checkout -- . && rmdir /S /Q src\redteam_mcp\webui\templates 2>nul
skill_id: rfc-007-htmx-base
---

# RFC-007 — htmx + Tailwind base layout

## Mission

在 FastAPI 里挂 Jinja2；提供 `base.html.j2` 骨架（含 htmx CDN + Tailwind CDN + nav）；`/` 返回 HTML dashboard。

## Context

- RFC-006 让 `/` 返回 JSON。本 RFC 改成 HTML。
- 采用零 build-step 方案：htmx + Alpine + Tailwind 全 CDN 引入。
- 未来 RFC 逐个 route 加页面，复用这套 base。

## Non-goals

- 不引入 npm / vite / webpack
- 不做 Dark mode toggle（未来小 RFC）
- 不做国际化

## Design

模板目录 `src/redteam_mcp/webui/templates/`。`templating.py` 暴露 `Jinja2Templates` 实例。

`base.html.j2` 提供：
- `<head>` 含 htmx 2.0 / Alpine 3 / Tailwind play CDN
- `{% block content %}` 供子模板填充
- `{% block title %}` 默认 "kestrel-mcp"
- 顶部 nav（dashboard / engagements / tools / settings）

## Steps

### Step 1 — 补依赖

```
RUN .venv\Scripts\python.exe -c "import jinja2" 2>nul || echo NEED_JINJA
```

如果缺失：

```
REPLACE pyproject.toml
<<<<<<< SEARCH
    "uvicorn[standard]>=0.32",
]
=======
    "uvicorn[standard]>=0.32",
    "jinja2>=3.1",
]
>>>>>>> REPLACE
```

```
RUN .venv\Scripts\python.exe -m uv lock
RUN .venv\Scripts\python.exe -m uv sync --frozen
```

### Step 2 — templating.py

```
WRITE src/redteam_mcp/webui/templating.py
```
```python
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
```

### Step 3 — base.html.j2

```
WRITE src/redteam_mcp/webui/templates/base.html.j2
```
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{% block title %}kestrel-mcp{% endblock %}</title>
  <script src="https://unpkg.com/htmx.org@2.0.4"
          integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+"
          crossorigin="anonymous"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    [x-cloak] { display: none !important; }
  </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen flex flex-col">
  {% include "_nav.html.j2" %}
  <main class="flex-1 max-w-6xl w-full mx-auto p-6">
    {% block content %}{% endblock %}
  </main>
  <footer class="text-center text-xs text-slate-400 py-4">
    kestrel-mcp · {{ now }}
  </footer>
</body>
</html>
```

### Step 4 — _nav.html.j2

```
WRITE src/redteam_mcp/webui/templates/_nav.html.j2
```
```html
<nav class="bg-white border-b border-slate-200 shadow-sm">
  <div class="max-w-6xl mx-auto flex items-center gap-6 px-6 h-14">
    <a href="/" class="font-semibold text-slate-800">kestrel-mcp</a>
    <a href="/engagements" class="text-sm text-slate-600 hover:text-slate-900">Engagements</a>
    <a href="/tools" class="text-sm text-slate-600 hover:text-slate-900">Tools</a>
    <a href="/settings" class="text-sm text-slate-600 hover:text-slate-900">Settings</a>
    <span class="flex-1"></span>
    {% if active_engagement %}
      <span class="text-xs px-2 py-1 rounded bg-emerald-100 text-emerald-800">{{ active_engagement.name }}</span>
    {% else %}
      <span class="text-xs px-2 py-1 rounded bg-slate-100 text-slate-500">no active engagement</span>
    {% endif %}
  </div>
</nav>
```

### Step 5 — dashboard.html.j2

```
WRITE src/redteam_mcp/webui/templates/dashboard.html.j2
```
```html
{% extends "base.html.j2" %}
{% block title %}Dashboard · kestrel-mcp{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">Dashboard</h1>
<p class="text-sm text-slate-600 mb-6">Welcome. {{ engagement_count }} engagement(s) on record.</p>

<div class="grid grid-cols-3 gap-4">
  <a href="/engagements" class="block p-4 rounded-xl bg-white border hover:shadow">
    <div class="text-xs text-slate-500">Engagements</div>
    <div class="text-2xl font-bold">{{ engagement_count }}</div>
  </a>
  <a href="/tools" class="block p-4 rounded-xl bg-white border hover:shadow">
    <div class="text-xs text-slate-500">Tools (MCP)</div>
    <div class="text-2xl font-bold">57</div>
  </a>
  <a href="/settings" class="block p-4 rounded-xl bg-white border hover:shadow">
    <div class="text-xs text-slate-500">Settings</div>
    <div class="text-2xl font-bold">&rarr;</div>
  </a>
</div>
{% endblock %}
```

### Step 6 — 改 app.py 让 `/` 返 HTML

```
REPLACE src/redteam_mcp/webui/app.py
<<<<<<< SEARCH
from fastapi import Depends, FastAPI

from ..core import RequestContext, ServiceContainer
from .deps import get_ctx
from .middleware import RequestContextMiddleware
=======
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse

from ..core import RequestContext, ServiceContainer
from .deps import get_ctx
from .middleware import RequestContextMiddleware
from .templating import templates
>>>>>>> REPLACE
```

```
REPLACE src/redteam_mcp/webui/app.py
<<<<<<< SEARCH
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, object]:
        return {"ok": True, "service": "kestrel-mcp web"}
=======
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def root(request: Request, ctx: RequestContext = Depends(get_ctx)):
        engagements = await ctx.engagement.list()
        return templates.TemplateResponse(
            "dashboard.html.j2",
            {
                "request": request,
                "engagement_count": len(engagements),
                "active_engagement": None,
                "now": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
        )

    @app.get("/__healthz", include_in_schema=False)
    async def healthz():
        return {"ok": True}
>>>>>>> REPLACE
```

### Step 7 — 测试

```
WRITE tests/unit/webui/test_html_smoke.py
```
```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from redteam_mcp.core import ServiceContainer
from redteam_mcp.webui import create_app


@pytest.fixture
async def client():
    c = ServiceContainer.in_memory()
    await c.initialise()
    app = create_app(c)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        yield cl
    await c.dispose()


async def test_root_html(client):
    r = await client.get("/")
    assert r.status_code == 200
    text = r.text
    assert "<!doctype html>" in text.lower()
    assert "kestrel-mcp" in text
    assert "htmx.org" in text
    assert "tailwindcss" in text


async def test_healthz(client):
    r = await client.get("/__healthz")
    assert r.json() == {"ok": True}


async def test_engagements_nav_present(client):
    r = await client.get("/")
    assert "/engagements" in r.text
    assert "/tools" in r.text
```

### Step 8 — full_verify

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Post-checks

- [ ] 3 测试绿
- [ ] 浏览器访问 `http://localhost:8765/` 能看到 dashboard（Step 8 是启动测试）
- [ ] 没新增 node_modules / package.json（零 build step 原则）

## Updates to other docs

`CHANGELOG.md` + `MASTER_PLAN` Sprint 4 Day 2 勾。

## Notes for executor

- htmx / Alpine / Tailwind 都走 CDN；CI 测试里不访问外网，只检查 HTML 里的 `<script src>` 字符串存在即可。
- Tailwind play CDN 不适合生产；未来 RFC 会改成预编译。现阶段追求「能跑能看」。

## Changelog

- **2026-04-21 初版**
