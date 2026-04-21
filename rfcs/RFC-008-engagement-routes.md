---
id: RFC-008
title: Engagement routes + templates (list / create / show)
epic: C-WebUI-Tier1
status: done
owner: agent
role: fullstack-engineer
blocking_on: [RFC-007]
budget:
  max_files_touched: 7
  max_new_files: 6
  max_lines_added: 400
  max_minutes_human: 30
  max_tokens_model: 16000
files_to_read:
  - src/kestrel_mcp/webui/app.py
  - src/kestrel_mcp/webui/templating.py
  - src/kestrel_mcp/domain/services/engagement_service.py
files_will_touch:
  - src/kestrel_mcp/webui/routes/__init__.py           # new
  - src/kestrel_mcp/webui/routes/engagements.py        # new
  - src/kestrel_mcp/webui/templates/engagements/list.html.j2     # new
  - src/kestrel_mcp/webui/templates/engagements/show.html.j2     # new
  - src/kestrel_mcp/webui/templates/engagements/_form.html.j2    # new (htmx partial)
  - src/kestrel_mcp/webui/app.py                       # modified (include router)
  - tests/unit/webui/test_engagement_routes.py         # new
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/webui/test_engagement_routes.py -v
rollback_cmd: git checkout -- . && rmdir /S /Q src\kestrel_mcp\webui\routes 2>nul && rmdir /S /Q src\kestrel_mcp\webui\templates\engagements 2>nul
skill_id: rfc-008-engagement-routes
---

# RFC-008 — Engagement routes

## Mission

网页列表 / 查看 / 创建 engagement。用 htmx 实现表单局部刷新，不整页 reload。

## Context

- Engagement 是核心业务实体。Web UI 第一个真正的「功能」页。
- 复用 `EngagementService`，不绕过。
- htmx: form submit 返回 HTML fragment 插入表格。

## Non-goals

- 不做状态转换按钮（留 RFC-009 或 D01）
- 不做 scope / finding / target 子页（分开 RFC）
- 不做搜索 / 分页（数据量小，先不做）

## Design

routes 包结构：
```
routes/
  __init__.py  ← 聚合 router
  engagements.py
```

URL 结构：
| Method | Path | 返回 |
|--------|------|-----|
| GET | /engagements | list HTML |
| POST | /engagements | create + 返回 row HTML (htmx target) |
| GET | /engagements/{slug} | detail HTML |
| DELETE | /engagements/{slug}?confirm=true | 暂不支持 (Tier 2) |

## Steps

### Step 1 — routes 包

```
WRITE src/kestrel_mcp/webui/routes/__init__.py
```
```python
from fastapi import APIRouter

from .engagements import router as engagements_router

router = APIRouter()
router.include_router(engagements_router, prefix="/engagements", tags=["engagements"])
```

### Step 2 — engagements.py

```
WRITE src/kestrel_mcp/webui/routes/engagements.py
```
```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ...core import RequestContext
from ...domain import entities as ent
from ...domain.errors import EngagementNotFoundError, UniqueConstraintError
from ..deps import get_ctx
from ..templating import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def list_engagements(
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
):
    engagements = await ctx.engagement.list()
    return templates.TemplateResponse(
        request,
        "engagements/list.html.j2",
        {"engagements": engagements, "active_engagement": None},
    )


@router.post("/", response_class=HTMLResponse)
async def create_engagement(
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
    name: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    client: Annotated[str, Form()],
    engagement_type: Annotated[str, Form()] = "ctf",
):
    try:
        e = await ctx.engagement.create(
            name=name,
            display_name=display_name,
            engagement_type=ent.EngagementType(engagement_type),
            client=client,
        )
    except UniqueConstraintError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc))

    # htmx partial: just the new row
    return templates.TemplateResponse(
        request,
        "engagements/_form.html.j2",
        {"engagement": e, "append_row": True},
    )


@router.get("/{slug}", response_class=HTMLResponse)
async def show_engagement(
    slug: str,
    request: Request,
    ctx: Annotated[RequestContext, Depends(get_ctx)],
):
    try:
        e = await ctx.engagement.get_by_name(slug)
    except EngagementNotFoundError:
        raise HTTPException(404, f"Engagement '{slug}' not found")
    scope = await ctx.scope.list_entries(e.id)
    findings = await ctx.finding.list_for_engagement(e.id)
    targets = await ctx.target.list_for_engagement(e.id)
    return templates.TemplateResponse(
        request,
        "engagements/show.html.j2",
        {
            "engagement": e,
            "scope": scope,
            "findings": findings,
            "targets": targets,
            "active_engagement": e,
        },
    )
```

### Step 3 — list.html.j2

```
WRITE src/kestrel_mcp/webui/templates/engagements/list.html.j2
```
```html
{% extends "base.html.j2" %}
{% block title %}Engagements · kestrel-mcp{% endblock %}
{% block content %}
<h1 class="text-2xl font-semibold mb-4">Engagements</h1>

<div class="mb-6 bg-white border rounded-xl p-4">
  <h2 class="text-sm font-medium mb-3">New engagement</h2>
  <form hx-post="/engagements" hx-target="#engagement-table tbody" hx-swap="beforeend"
        class="grid grid-cols-4 gap-3 text-sm">
    <input name="name" required placeholder="slug (a-z0-9-_)" pattern="^[a-z0-9_-]{1,64}$"
           class="border rounded px-2 py-1">
    <input name="display_name" required placeholder="Display name"
           class="border rounded px-2 py-1">
    <select name="engagement_type" class="border rounded px-2 py-1">
      <option value="ctf">CTF</option>
      <option value="pentest">Pentest</option>
      <option value="red_team">Red Team</option>
      <option value="bug_bounty">Bug Bounty</option>
    </select>
    <input name="client" required placeholder="Client"
           class="border rounded px-2 py-1">
    <button type="submit"
            class="col-span-4 justify-self-start bg-slate-800 text-white px-4 py-1 rounded">Create</button>
  </form>
</div>

<div class="bg-white border rounded-xl overflow-hidden">
  <table id="engagement-table" class="w-full text-sm">
    <thead class="bg-slate-50">
      <tr>
        <th class="px-3 py-2 text-left">Name</th>
        <th class="px-3 py-2 text-left">Status</th>
        <th class="px-3 py-2 text-left">Type</th>
        <th class="px-3 py-2 text-left">Client</th>
        <th class="px-3 py-2"></th>
      </tr>
    </thead>
    <tbody>
      {% for e in engagements %}
        {% include "engagements/_form.html.j2" with context %}
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### Step 4 — _form.html.j2 (partial row)

```
WRITE src/kestrel_mcp/webui/templates/engagements/_form.html.j2
```
```html
{# rendered both as a full row (in list.html.j2) and as htmx partial response #}
{% set e = engagement if engagement is defined else e %}
<tr class="border-t">
  <td class="px-3 py-2 font-medium">
    <a class="text-blue-700 hover:underline" href="/engagements/{{ e.name }}">{{ e.name }}</a>
    <div class="text-xs text-slate-500">{{ e.display_name }}</div>
  </td>
  <td class="px-3 py-2">
    <span class="text-xs px-2 py-0.5 rounded
      {% if e.status.value == 'active' %}bg-emerald-100 text-emerald-800
      {% elif e.status.value == 'closed' %}bg-slate-100 text-slate-500
      {% else %}bg-amber-100 text-amber-800{% endif %}
    ">{{ e.status.value }}</span>
  </td>
  <td class="px-3 py-2">{{ e.engagement_type.value }}</td>
  <td class="px-3 py-2">{{ e.client }}</td>
  <td class="px-3 py-2 text-right">
    <a href="/engagements/{{ e.name }}" class="text-xs text-slate-600 hover:text-slate-900">view →</a>
  </td>
</tr>
```

### Step 5 — show.html.j2

```
WRITE src/kestrel_mcp/webui/templates/engagements/show.html.j2
```
```html
{% extends "base.html.j2" %}
{% block title %}{{ engagement.name }} · kestrel-mcp{% endblock %}
{% block content %}
<a href="/engagements" class="text-xs text-slate-500">← back</a>
<h1 class="text-2xl font-semibold mt-2">{{ engagement.display_name }}</h1>
<div class="text-sm text-slate-500">slug: <code>{{ engagement.name }}</code> · status:
  <strong>{{ engagement.status.value }}</strong> · type: {{ engagement.engagement_type.value }}</div>

<div class="grid grid-cols-3 gap-4 mt-6">
  <div class="p-4 bg-white border rounded-xl">
    <div class="text-xs text-slate-500">Scope entries</div>
    <div class="text-2xl font-bold">{{ scope|length }}</div>
  </div>
  <div class="p-4 bg-white border rounded-xl">
    <div class="text-xs text-slate-500">Targets</div>
    <div class="text-2xl font-bold">{{ targets|length }}</div>
  </div>
  <div class="p-4 bg-white border rounded-xl">
    <div class="text-xs text-slate-500">Findings</div>
    <div class="text-2xl font-bold">{{ findings|length }}</div>
  </div>
</div>

{% if findings %}
<h2 class="text-lg font-medium mt-8 mb-2">Recent findings</h2>
<ul class="bg-white border rounded-xl divide-y text-sm">
  {% for f in findings[:10] %}
  <li class="px-3 py-2 flex items-center">
    <span class="text-xs px-2 py-0.5 rounded mr-3
      {% if f.severity.value == 'critical' %}bg-red-100 text-red-800
      {% elif f.severity.value == 'high' %}bg-orange-100 text-orange-800
      {% elif f.severity.value == 'medium' %}bg-amber-100 text-amber-800
      {% elif f.severity.value == 'low' %}bg-sky-100 text-sky-800
      {% else %}bg-slate-100 text-slate-600{% endif %}
    ">{{ f.severity.value }}</span>
    <span class="font-medium">{{ f.title }}</span>
    <span class="ml-auto text-xs text-slate-400">{{ f.status.value }}</span>
  </li>
  {% endfor %}
</ul>
{% endif %}
{% endblock %}
```

### Step 6 — 装载 router

```
REPLACE src/kestrel_mcp/webui/app.py
<<<<<<< SEARCH
    app.add_middleware(RequestContextMiddleware, container=container)
=======
    app.add_middleware(RequestContextMiddleware, container=container)

    from .routes import router as api_router
    app.include_router(api_router)
>>>>>>> REPLACE
```

### Step 7 — 测试

```
WRITE tests/unit/webui/test_engagement_routes.py
```
```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from kestrel_mcp.core import ServiceContainer
from kestrel_mcp.domain import entities as ent
from kestrel_mcp.webui import create_app


@pytest.fixture
async def setup():
    c = ServiceContainer.in_memory()
    await c.initialise()
    app = create_app(c)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        yield cl, c
    await c.dispose()


async def test_list_empty(setup):
    client, _ = setup
    r = await client.get("/engagements/")
    assert r.status_code == 200
    assert "Engagements" in r.text
    assert "New engagement" in r.text


async def test_create_engagement(setup):
    client, _ = setup
    r = await client.post("/engagements/", data={
        "name": "web-test",
        "display_name": "Web Test",
        "engagement_type": "ctf",
        "client": "Demo",
    })
    assert r.status_code == 200
    assert "web-test" in r.text
    assert "planning" in r.text


async def test_create_duplicate_409(setup):
    client, c = setup
    await c.engagement.create(
        name="dup", display_name="x",
        engagement_type=ent.EngagementType.CTF, client="c",
    )
    r = await client.post("/engagements/", data={
        "name": "dup", "display_name": "x",
        "engagement_type": "ctf", "client": "c",
    })
    assert r.status_code == 409


async def test_show_page(setup):
    client, c = setup
    await c.engagement.create(
        name="detail-test", display_name="Detail Test",
        engagement_type=ent.EngagementType.CTF, client="c",
    )
    r = await client.get("/engagements/detail-test")
    assert r.status_code == 200
    assert "Detail Test" in r.text
    assert "Scope entries" in r.text


async def test_show_404(setup):
    client, _ = setup
    r = await client.get("/engagements/nope")
    assert r.status_code == 404
```

### Step 8 — full_verify

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Post-checks

- [ ] 5 个新测试绿
- [ ] 浏览器 `localhost:8765/engagements` 能看到表格 + 表单
- [ ] 提交表单后新行 append（不整页 reload）—— htmx 工作

## Notes for executor

- 表单 `hx-target` 指向 `#engagement-table tbody`，`hx-swap="beforeend"` 把新 row append。
- `_form.html.j2` 既被 include 循环，又作为 POST 响应 —— 所以同时兼容 `engagement` 和 `e` 变量名（Jinja `{% set e = engagement if engagement is defined else e %}`）。
- 模板里用 `engagement.name` 不要用 `engagement.id`（slug 更友好，URL 更干净）。

## Changelog

- **2026-04-21 初版**
