# RFC Stubs — Epic B / D / E / F / G / H

> 这 28 个 RFC 目前是「骨架」：有 mission、依赖、粗略 steps，够 reviewer 判断优先级和范围。
> 到各自执行顺序时，把单个 stub 展开成 `rfcs/RFC-XXX-<slug>.md` 独立文件（模板 RFC-000）。
> 所有 stub 共享 verify_cmd 底线：`scripts/full_verify.py` 必须绿。

---

## Epic B — Core hardening

### RFC-B01 — Propagate core_errors everywhere

- **Mission**: 所有 `except Exception` 收拢到 `core_errors.KestrelError` 子类；MCP server 和 (未来的) REST 层统一 render。
- **Blocking**: RFC-002
- **Budget**: 6 files, 200 lines
- **Steps 摘要**:
  1. 全项目 grep `except Exception` —— 每处判断是 user / system / external，改成对应子类 raise
  2. `server.py` 的 dispatcher 给每类异常渲染不同消息模板
  3. 测试：每种错误路径各 1 case
- **Closes**: GAP G-E1

### RFC-B02 — Rich guidance for remaining 5 tool modules

- **Mission**: `caido_tool / ligolo_tool / sliver_tool / havoc_tool / evilginx_tool` 每个 tool 补 `when_to_use` / `pitfalls` / `local_model_hints`（shodan_tool.py 已做模板）。
- **Blocking**: 无
- **Budget**: 5 files, ~400 lines 纯字符串
- **Steps**: 逐模块 REPLACE ToolSpec 实例添加字段，参考 shodan 格式。
- **Closes**: AUDIT D-12

### RFC-B03 — THREAT_MODEL status tracking

- **Mission**: THREAT_MODEL.md 每个威胁加 `status: open | partial | done`，并加 `mitigated_by: [RFC-xxx]` 字段。
- **Blocking**: 无
- **Budget**: 1 file, ~50 lines
- **Steps**: 逐个威胁小节 append status 行。
- **Closes**: AUDIT D-13

### RFC-B04 — Log event schema versioning

- **Mission**: `logging.py` 的 `audit_event` 换成结构化事件（Pydantic model → JSON）；加 `event_schema_version` 字段。
- **Blocking**: RFC-B01
- **Budget**: 4 files
- **Steps**:
  1. 定义 `logging.events.ToolCallEvent / ScopeCheckEvent / ...` Pydantic models
  2. `audit_event(...)` 改成 `emit(event: Event)`
  3. 逐处 call site 改签名
- **Closes**: GAP G-E6

### RFC-B05 — Secret backends (keychain / vault)

- **Mission**: 扩展 `CredentialService._resolve_key` 的策略链，支持 macOS Keychain / Windows CredMan / Vault。
- **Blocking**: RFC-003
- **Budget**: 6 files, 350 lines
- **Steps**:
  1. 定义 `SecretBackend` Protocol
  2. 实现 `KeychainBackend` (用 `keyring>=25`)、`VaultBackend` (httpx)
  3. 配置里按优先级链
- **Closes**: GAP G-A6

### RFC-B06 — Tool degradation on missing binary

- **Mission**: 启动时 detect 缺失的 tool binary，标记 module unhealthy，不注册 spec；Doctor 显示 `unhealthy` 状态。
- **Blocking**: 无
- **Budget**: 3 files, 100 lines
- **Steps**:
  1. `ToolModule.enabled()` 加 `self.is_healthy()` 检查
  2. 缺失 binary 时 `enabled()` 返回 False + warn log
  3. Doctor CLI 区分 `disabled` vs `unhealthy`
- **Closes**: GAP G-A8

---

## Epic D — Web UI Tier 2

### RFC-D01 — Markdown editor (Milkdown)

- **Mission**: `/reports/new` 提供 Markdown 编辑器（Milkdown CDN），支持插入 finding 引用（`{{finding:xxxx}}`）。
- **Blocking**: RFC-009
- **Budget**: 5 files, 400 lines
- **Steps**:
  1. 新 route `/reports/new`
  2. Milkdown CDN import
  3. Finding picker（htmx search）
  4. POST save → 存 Artifact
- **Closes**: GAP G-U7 partial

### RFC-D02 — PDF export via WeasyPrint

- **Mission**: `/reports/{id}/export.pdf` 把 Markdown 经 HTML 转 PDF。
- **Blocking**: RFC-D01
- **Budget**: 3 files, 150 lines
- **Steps**:
  1. 依赖 `weasyprint>=62` + Linux 上 `libpango` (CI 文档)
  2. 路由 read artifact → markdown-it 渲染 HTML → WeasyPrint → PDF stream
- **Notes**: Windows 上 WeasyPrint 难装；用 `--format=html` 作为 fallback，PDF 只 Linux/macOS 保证。

### RFC-D03 — Credentials vault UI

- **Mission**: `/credentials` 页：列表（脱敏）、「Reveal」按钮（二次确认 + 密码登录后才解密）。
- **Blocking**: RFC-003
- **Budget**: 5 files, 350 lines
- **Steps**:
  1. `routes/credentials.py`
  2. Reveal endpoint 要求 HTTP Basic 或 session（RFC-012 开启）
  3. Reveal 后的值只在响应 HTML 中一次性显示，不缓存

### RFC-D04 — Audit log viewer

- **Mission**: `/audit` 页：查 `~/.kestrel/logs/server.log` 的 JSON line，支持 tool name / engagement / time 过滤。
- **Blocking**: RFC-008
- **Budget**: 4 files, 250 lines

---

## Epic E — Web UI Tier 3

### RFC-E01 — Cytoscape attack graph

- **Mission**: `/engagements/{slug}/graph`：Cytoscape.js 画 Target↔Session↔Credential↔Finding 关系图。
- **Blocking**: RFC-008
- **Budget**: 5 files, 400 lines
- **Steps**:
  1. 数据端点 `/api/v1/engagements/{slug}/graph` → JSON {nodes, edges}
  2. Cytoscape CDN + dagre layout
  3. Node click → 右侧 drawer 显示详情
- **Notes**: 图密度大时要分页 / 聚类 —— 暂不做。

### RFC-E02 — Timeline (gantt) view

- **Mission**: ToolInvocation 按时间轴展示，类似 VS Code 的 `git blame` 时间线。
- **Blocking**: RFC-D04
- **Budget**: 4 files

### RFC-E03 — Event bus + WebSocket push

- **Mission**: 内部 pub/sub：tool 完成 / 新 finding → 推到所有订阅的浏览器。
- **Blocking**: RFC-010
- **Budget**: 6 files, 500 lines
- **Notes**: 这是 Tier 3 最重的一个；RFC 展开时要细拆成 E03a/E03b。

---

## Epic F — TUI (Textual)

### RFC-F01 — Textual skeleton + nav

- **Mission**: `kestrel-mcp tui` 启动 Textual，左侧 nav（Engagements / Tools / Audit），右侧 content area。
- **Blocking**: RFC-002
- **Budget**: 5 files
- **Steps**:
  1. `pyproject.toml` 加 `textual>=0.80`
  2. `src/kestrel_mcp/tui/__init__.py` + `app.py`
  3. 加 CLI subcommand `kestrel-mcp tui`

### RFC-F02 — Engagement + Finding views

- **Mission**: 在 TUI 里 list/show engagement 和 finding，键盘驱动。
- **Blocking**: RFC-F01
- **Budget**: 6 files

### RFC-F03 — Tool runner via TUI

- **Mission**: TUI 里选 tool、填参数、tail stdout；不做 SSE（本地直接订阅 Job queue）。
- **Blocking**: RFC-F02, RFC-010

---

## Epic G — Tool expansion

每个工具 RFC 都遵循 `shodan_tool.py` / `nuclei_tool.py` 的模板：
- `ToolModule` 子类
- 每个 tool `ToolSpec` 带 rich guidance
- 至少 3 测试（handler happy / 错误 / scope 拒绝）
- 加到 `tools/__init__.py` 的 `load_modules`
- 更新 TOOLS_MATRIX.md

### RFC-G01 — subfinder tool

- **Mission**: `subfinder_enum(domain, all_sources)` + `subfinder_version`
- **Binary**: projectdiscovery/subfinder
- **Budget**: 3 files, 300 lines
- **Tests**: mock subprocess + 1 real integration test（有 binary 时）

### RFC-G02 — httpx probe tool

- **Mission**: `httpx_probe(targets, tech_detect, status_code)`
- **Binary**: projectdiscovery/httpx
- **Blocking**: RFC-G01（顺序，不 hard 依赖）
- **Budget**: 3 files, 280 lines

### RFC-G03 — nmap wrapper

- **Mission**: `nmap_scan(targets, ports, scripts)` + `nmap_os_detect`
- **Binary**: nmap
- **Notes**: 输出解析用 `python-nmap>=0.7` 依赖。Windows 需 npcap。

### RFC-G04 — ffuf wrapper

- **Mission**: `ffuf_dir_bruteforce(url, wordlist)`、`ffuf_param_fuzz`
- **Binary**: ffuf/ffuf

### RFC-G05 — Metasploit RPC client

- **Mission**: `msf_list_modules`, `msf_run_exploit`, `msf_list_sessions`, `msf_interact`
- **Binary**: msfrpcd（用户启动）
- **Blocking**: RFC-003 (credentials for MSF session)
- **Budget**: 8 files, 800 lines — 独立 epic-sized。**展开时必须拆成 G05a/b/c**。

### RFC-G06 — Impacket scripts (top 5)

- **Mission**: 封装 `psexec.py`, `smbexec.py`, `wmiexec.py`, `secretsdump.py`, `GetUserSPNs.py`
- **Binary**: `python -m impacket.examples.<script>` (pip 依赖)
- **Budget**: 6 files

### RFC-G07 — NetExec wrapper

- **Mission**: `netexec_smb(target, creds)` 等
- **Binary**: NetExec (pipx)
- **Blocking**: RFC-003

### RFC-G08 — BloodHound-CE REST client

- **Mission**: 从 BloodHound-CE 容器拉取 AD 图分析结果
- **Binary**: docker-compose (用户自己起)
- **Budget**: 5 files

---

## Epic H — Release & community

### RFC-H01 — Rename to kestrel-mcp

- **Mission**: 项目大改名：package / CLI / docs。
- **Blocking**: RFC-002
- **Budget**: 30+ files (sed-like replace)
- **Steps**:
  1. grep `kestrel_mcp` 全替换 `kestrel_mcp`
  2. `pyproject.toml` name 改
  3. venv 重新创建
  4. 验证 all tests green
- **Notes**: 必须一次 PR 完成，否则 import 断。
- **Closes**: AUDIT D-1

### RFC-H02 — PyPI + Docker release pipeline

- **Mission**: `release.yml` GitHub Action：tag → PyPI + GHCR + GitHub Release changelog
- **Blocking**: RFC-H01, RFC-002
- **Budget**: 4 files
- **Steps**:
  1. `.github/workflows/release.yml`
  2. `Dockerfile`（distroless-like 或 python:slim）
  3. `docs/releasing.md`

### RFC-H03 — MkDocs Material site

- **Mission**: 搭 docs 站点；host 到 GitHub Pages。
- **Blocking**: RFC-H01
- **Budget**: 10 files, 大量 reorg

### RFC-H04 — v1.0 release gate + announcement

- **Mission**: 发 v1.0。含 release checklist。
- **Blocking**: 所有上面的

---

## 状态同步

每次把 stub 展开成独立 RFC 时：

1. 在 `rfcs/` 新建 `RFC-XXX-<slug>.md`（按 RFC-000-TEMPLATE）
2. 从本文件删除对应 stub
3. 更新 `rfcs/INDEX.md` 行
4. commit message: `RFC-XXX: expand stub`

---

## Changelog

- **2026-04-21 初版** — 所有 stub 初稿，等待逐个展开。
