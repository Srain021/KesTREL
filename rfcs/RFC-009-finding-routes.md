---
id: RFC-009
title: Findings table + transitions
epic: C-WebUI-Tier1
status: done
owner: agent
role: fullstack-engineer
blocking_on: [RFC-008]
budget:
  max_files_touched: 5
  max_new_files: 4
  max_lines_added: 350
  max_minutes_human: 25
  max_tokens_model: 14000
files_to_read:
  - src/redteam_mcp/webui/routes/engagements.py
  - src/redteam_mcp/domain/services/finding_service.py
files_will_touch:
  - src/redteam_mcp/webui/routes/findings.py              # new
  - src/redteam_mcp/webui/routes/__init__.py              # modified
  - src/redteam_mcp/webui/templates/findings/table.html.j2  # new
  - src/redteam_mcp/webui/templates/findings/_row.html.j2   # new (htmx partial)
  - tests/unit/webui/test_finding_routes.py               # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/webui/test_finding_routes.py -v
rollback_cmd: git checkout -- . && rmdir /S /Q src\redteam_mcp\webui\templates\findings 2>nul
skill_id: rfc-009-findings
---

# RFC-009 — Findings table + transitions

## Mission

`/engagements/{slug}/findings` 页：severity 过滤、htmx 行内状态切换。

## Steps（摘要，与 RFC-008 同构）

1. `routes/findings.py` — 新 router，前缀 `/engagements/{slug}/findings`。3 个路由：
   - `GET /` → 渲染 table（支持 `?severity=critical&status=new` 查询参数）
   - `POST /{finding_id}/transition` → 调 `finding.transition`，返回 `_row.html.j2`
   - `GET /{finding_id}` → 详情页（stretch，可缺省）

2. `templates/findings/table.html.j2` — 表头、过滤器按钮（severity critical/high/medium/low/info）、tbody 迭代 `_row.html.j2`

3. `templates/findings/_row.html.j2` — 单行，含状态 dropdown `<form hx-post="...">` 触发转换

4. `routes/__init__.py` 加 `include_router(findings_router, prefix="/engagements/{slug}/findings")`

5. 测试：seed engagement + target + 3 findings → GET list → POST transition → 校验 DB 变化

## verify_cmd

见 front-matter。

## Notes

- 状态转换的 form action：`hx-post="/engagements/{{ slug }}/findings/{{ f.id }}/transition"`, `hx-target="closest tr"`, `hx-swap="outerHTML"`.
- 参考 DOMAIN_MODEL §3.6 的 finding 状态机；非法转换返回 409。
- Filter query 参数用 `ctx.finding.list_for_engagement(status=..., severity=...)`，已支持。

## Changelog

- **2026-04-21 初版（骨架）**
