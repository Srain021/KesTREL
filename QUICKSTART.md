# Quickstart — 在你的机器上启动 kestrel-mcp

## 你现在拥有的

* **34 个文件 / ~180 KB 源码**（全部写完、全部通过语法校验）
* **41 个 MCP tools**，分布在 7 个工具模块 + 2 个 workflow
* **静态分析全部通过**（29 个 .py 文件 0 错误）

## 一张图看懂目录结构

```
kestrel-mcp/
├── pyproject.toml            # 项目声明 + 依赖
├── README.md                 # 完整说明书
├── QUICKSTART.md             # 本文件
├── LICENSE                   # MIT + 责任声明
├── .env.example              # 环境变量模板
├── MANIFEST.in               # 打包清单
│
├── config/
│   ├── default.yaml          # 默认配置
│   └── cursor-mcp.json.example  # Cursor MCP 配置模板
│
├── scripts/
│   ├── install.ps1           # Windows 一键安装
│   ├── install.sh            # Linux/macOS 一键安装
│   ├── install-deps-fast.ps1 # 慢网络分层安装
│   └── register_cursor.py    # 自动注册到 Cursor
│
├── src/kestrel_mcp/
│   ├── __init__.py
│   ├── __main__.py           # CLI 入口 (kestrel-mcp 命令)
│   ├── server.py             # MCP 服务器
│   ├── config.py             # 配置加载（YAML+ENV）
│   ├── logging.py            # 结构化日志 + 审计
│   ├── security.py           # ScopeGuard 权限检查
│   ├── executor.py           # 异步子进程执行器
│   │
│   ├── tools/                # 7 个工具模块共 36 个 tools
│   │   ├── base.py           # ToolModule / ToolSpec / ToolResult
│   │   ├── shodan_tool.py    # 6 tools
│   │   ├── nuclei_tool.py    # 5 tools
│   │   ├── caido_tool.py     # 4 tools
│   │   ├── ligolo_tool.py    # 5 tools
│   │   ├── sliver_tool.py    # 8 tools
│   │   ├── havoc_tool.py     # 6 tools
│   │   └── evilginx_tool.py  # 5 tools
│   │
│   ├── workflows/            # 高阶组合流程
│   │   ├── recon.py          # recon_target 工作流
│   │   └── report.py         # generate_pentest_report
│   │
│   ├── parsers/              # (Phase 2) 输出解析器
│   ├── resources/            # (Phase 2) MCP resources
│   └── prompts/              # (Phase 2) MCP prompts
│
└── tests/
    ├── test_security.py       # 11 个 ScopeGuard 测试
    ├── test_config.py         # 配置层叠 & env override
    ├── test_executor.py       # 子进程超时/截断
    └── test_tools_dispatch.py # 41 tools 注册/schema 校验
```

## 已经就绪的 MCP tools（41 个）

### 侦察 / 情报
* `shodan_search` · `shodan_host` · `shodan_count` · `shodan_facets` · `shodan_scan_submit` · `shodan_account_info`

### 漏洞扫描
* `nuclei_scan` · `nuclei_update_templates` · `nuclei_list_templates` · `nuclei_version` · `nuclei_validate_template`

### Web 代理
* `caido_start` · `caido_stop` · `caido_status` · `caido_replay_request`

### 内网穿透
* `ligolo_start_proxy` · `ligolo_stop_proxy` · `ligolo_proxy_status` · `ligolo_generate_agent_command` · `ligolo_add_route`

### C2 - Sliver
* `sliver_start_server` · `sliver_stop_server` · `sliver_server_status` · `sliver_run_command` · `sliver_list_sessions` · `sliver_list_listeners` · `sliver_generate_implant` · `sliver_execute_in_session`

### C2 - Havoc
* `havoc_build_teamserver` · `havoc_start_teamserver` · `havoc_stop_teamserver` · `havoc_teamserver_status` · `havoc_lint_profile` · `havoc_generate_demon_hint`

### 钓鱼
* `evilginx_start` · `evilginx_stop` · `evilginx_status` · `evilginx_list_phishlets` · `evilginx_list_captured_sessions`

### 高阶工作流
* `recon_target` — Shodan 证书发现 + 主机详情 + 可选 Nuclei 基线扫描
* `generate_pentest_report` — Markdown 渗透测试报告

---

## 当下剩下的唯一任务：装依赖

项目代码 100% 完成，缺的只是 pip 装依赖。网络稳定后执行以下之一：

### 方式 A：快速分层安装（推荐）
```powershell
cd "d:\TG PROJECT\kestrel-mcp"
powershell -ExecutionPolicy Bypass -File .\scripts\install-deps-fast.ps1
```

### 方式 B：标准 pip 安装
```powershell
cd "d:\TG PROJECT\kestrel-mcp"
pip install -e ".[dev]"
```

### 方式 C：最少核心（不含 GUI CLI/开发工具）
```powershell
pip install mcp pydantic pydantic-settings pyyaml anyio httpx shodan structlog rich typer python-dotenv jinja2
```

---

## 装完后立即验证

```powershell
# 1. CLI 能跑？
python -m kestrel_mcp version
#   0.1.0

# 2. 诊断所有工具
python -m kestrel_mcp doctor
#   ┌──────────┬─────────┬──────────────────┬──────────────┐
#   │ Tool     │ Enabled │ Binary           │ Status       │
#   ├──────────┼─────────┼──────────────────┼──────────────┤
#   │ shodan   │    ✔    │                  │ missing key  │
#   │ nuclei   │    ✔    │ .../nuclei.exe   │ ready        │
#   │ caido    │    ✘    │                  │ disabled     │
#   │ ...      │         │                  │              │
#   └──────────┴─────────┴──────────────────┴──────────────┘

# 3. 列出所有 MCP tools 的 JSON schema
python -m kestrel_mcp list-tools | more

# 4. 跑离线测试
pytest tests/test_security.py tests/test_config.py tests/test_executor.py tests/test_tools_dispatch.py -v

# 5. 配置 Cursor
python scripts\register_cursor.py --scope "*.lab.internal,127.0.0.1"
```

重启 Cursor，在聊天框输入：
> "用 shodan_count 查 `product:nginx country:US` 有多少"

Cursor 会自动选中 MCP 服务器里的 `shodan_count` 工具并返回结果。

---

## 安全默认值

* `authorized_scope=[]` → **所有攻击性工具拒绝运行**
* `dry_run=false` → 但可通过 `--dry-run` 或 ENV 打开
* `dangerous_ops_require_scope=true` → payload 生成、扫描、钓鱼都需要 scope 命中
* 每次 `call_tool` 写入 `~/.kestrel/audit.log`

---

## 常见故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `AUTHORIZATION DENIED: authorized_scope is empty` | 没配 scope | `export KESTREL_MCP_AUTHORIZED_SCOPE="*.lab"` |
| `ToolNotFoundError: 'nuclei' not found on PATH` | 二进制路径没配 | 在 `.env` 设 `KESTREL_MCP_TOOL_NUCLEI=/path/to/nuclei.exe` |
| pip 装包超慢 / 卡住 | Tailscale Exit Node 劫持路由 | `tailscale set --exit-node=` 临时关闭 |
| Shodan tools 报 "SHODAN_API_KEY is empty" | 没设 API Key | 在 https://account.shodan.io 获取并 `export SHODAN_API_KEY=xxx` |
| `tool.auth_denied` 日志 | 目标不在 scope 内 | 把目标加到 `KESTREL_MCP_AUTHORIZED_SCOPE` |
