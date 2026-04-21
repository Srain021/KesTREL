---
id: RFC-011
title: Settings page (API keys + tool binary paths)
epic: C-WebUI-Tier1
status: done
owner: agent
role: fullstack-engineer
blocking_on: [RFC-007]
budget:
  max_files_touched: 4
  max_new_files: 3
  max_lines_added: 250
  max_minutes_human: 20
  max_tokens_model: 10000
files_to_read:
  - src/kestrel_mcp/config.py
  - src/kestrel_mcp/__main__.py  # doctor 逻辑
files_will_touch:
  - src/kestrel_mcp/webui/routes/settings.py               # new
  - src/kestrel_mcp/webui/routes/__init__.py               # modified
  - src/kestrel_mcp/webui/templates/settings/page.html.j2  # new
  - tests/unit/webui/test_settings_routes.py               # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/webui/test_settings_routes.py -v
rollback_cmd: git checkout -- . && rmdir /S /Q src\kestrel_mcp\webui\templates\settings 2>nul
skill_id: rfc-011-settings-page
---

# RFC-011 — Settings page

## Mission

`/settings` 页：只读展示当前 config + env + doctor（重用既有逻辑），提示用户「要改就编辑 mcp.json 后重启」。

## Context

- 本 RFC 故意 **read-only**。
- 写入流程涉及 secret 管理（Vault / keychain），留给 RFC-D03。
- 用户看 settings 的主诉求：「我的 key 有效吗 / 哪些工具 ready」，这就是 doctor 的输出。

## Non-goals

- 不允许 Web UI 写 config 文件
- 不输出 API key 明文（只显示 `present` / `missing`）

## Steps（摘要）

1. `routes/settings.py`：`GET /settings` 渲染页面。
   - 调用 `load_settings()` 拿 Settings；转 dict；mask 掉 `SHODAN_API_KEY` 等敏感字段为 "present"/"missing"。
   - 复用 `__main__._resolve_path` 和 `_status_for` 的逻辑（或提取成 `webui.doctor_view`）

2. `settings/page.html.j2`：
   - 表格：Tool / Enabled / Binary / Status （doctor 同款）
   - 环境：Python / kestrel-mcp ver / Shodan key present / Scope count
   - 底部 link 到 `{ENV CONFIG PATH}` 但只复制，不改

3. 测试：
   - `GET /settings` 200
   - 响应 HTML 含 `"kestrel-mcp"`、`"Authorized scope"`
   - Key 字段 mask：响应不含真实的 `V8LdA4Fxi...`

## Notes

- 既有 `cli.__main__.doctor` 命令里用了 rich.Table 直接 print 到 stderr。要重构：把核心判断逻辑抽到 `kestrel_mcp.cli.readiness` 纯函数 `build_readiness_report() -> list[dict]`，`doctor` 和 settings route 都调它。
- 重构这一步可以放在 RFC-011 里，一起做（budget 留了余量）。

## verify_cmd

见 front-matter。

## Changelog

- **2026-04-21 初版（骨架）**
