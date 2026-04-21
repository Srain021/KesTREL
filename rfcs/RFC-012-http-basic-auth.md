---
id: RFC-012
title: HTTP Basic auth for shared deployment
epic: C-WebUI-Tier1
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-006]
budget:
  max_files_touched: 4
  max_new_files: 2
  max_lines_added: 200
  max_minutes_human: 15
  max_tokens_model: 8000
files_to_read:
  - src/kestrel_mcp/webui/app.py
  - src/kestrel_mcp/config.py
files_will_touch:
  - src/kestrel_mcp/webui/auth.py                 # new
  - src/kestrel_mcp/webui/app.py                  # modified
  - tests/unit/webui/test_auth.py                 # new
  - src/kestrel_mcp/config.py                     # modified (WebUISettings block)
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/webui/test_auth.py -v
rollback_cmd: git checkout -- . && del src\kestrel_mcp\webui\auth.py 2>nul
skill_id: rfc-012-basic-auth
---

# RFC-012 — HTTP Basic auth

## Mission

给 Web UI 加可选 HTTP Basic 认证，方便在局域网共享。默认关闭。

## Context

- 单用户本机使用：`--host 127.0.0.1` 已经安全。
- 团队共享（SSH 端口转发 / Tailscale）：至少要一道密码门。
- 不做 OIDC / SAML —— 那是 Pro 版。

## Design

Config 新块：

```yaml
webui:
  auth_required: false
  username: "kestrel"
  password_hash: ""   # argon2id hash; CLI 辅助命令生成
  session_cookie_name: "kestrel_session"
```

中间件：HTTP Basic only（MVP 够用）。启用时 `auth_required=true` + `password_hash` 非空。

Cli 新命令 `kestrel-mcp webui-set-password --password xxx` 生成 argon2id hash 并打印，用户粘贴到 mcp.json。（本 RFC 不实现命令 —— docstring 里教怎么用 `passlib` 手动生成。写到 `README.md` 里）

## Steps（摘要）

1. 加依赖：`argon2-cffi>=23.1`
2. 新建 `webui/auth.py`：`BasicAuthMiddleware`，从 settings 读 hash；校验请求头 `Authorization: Basic base64(user:pass)`
3. 改 `app.py`：如果 `settings.webui.auth_required` 则 `app.add_middleware(BasicAuthMiddleware, ...)`
4. 改 `config.py` 加 `WebUISettings` 字段
5. 测试：`auth_required=True` + 无 header → 401；正确 header → 200

## Skip if ...

- 用户明确说「就我一个人本地用」，可以 `auth_required=false` 完全跳过本 RFC 的启用。本 RFC 做的是「当需要开启时已就绪」。

## Changelog

- **2026-04-21 初版（骨架）**
