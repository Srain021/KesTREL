# UI STRATEGY

> 当前只有 MCP-over-stdio 一种交互方式（LLM 驱动）。
> 这份文档盘点 UI 选项、评估成本、给出分层推荐。
> 写于 domain model 和 plugin 系统落地之前，以便 UI 决策反过来影响后端 API 设计。

**Status**: 决策待定
**Author**: architecture team
**Reviewers**: @bofud

---

## 目录

1. [背景与现状](#1-背景与现状)
2. [用户画像](#2-用户画像)
3. [7 个技术选项](#3-7-个技术选项)
4. [成本矩阵](#4-成本矩阵)
5. [推荐方案](#5-推荐方案)
6. [分层架构（后端共用）](#6-分层架构后端共用)
7. [Web Dashboard 功能清单](#7-web-dashboard-功能清单)
8. [实施分阶段](#8-实施分阶段)
9. [技术栈细节](#9-技术栈细节)
10. [风险与 trade-off](#10-风险与-trade-off)
11. [等你决策的 4 件事](#11-等你决策的-4-件事)

---

## 1. 背景与现状

### 当前交互路径

```
User ──自然语言──► Cursor / Claude Desktop ──MCP stdio──► kestrel-mcp server ──► Tools
```

**能做什么**: 通过 LLM 自然语言调工具，LLM 自主规划、调用、汇总。
**不能做什么**:
- 看不到 engagement 整体状态（targets、findings 全在 LLM context 里，context 一满就忘）
- 看不到 tool 执行进度（同步等待，不展示 stdout 实时流）
- 无法并行监控多个 job
- 无法可视化攻击图（AD graph、网络拓扑）
- 非专业用户打开 Cursor 就懵
- 团队协作困难（一个人的 chat 别人看不到）
- 没法把数据"拉出来"再处理（Excel 导出、API 消费）

### 这些是不是"必须"解决？

不完全是。CTF 选手 + 专业红队大多用 CLI / IDE，**不一定要 GUI**。
但你说"对用户来说好用"= 扩展用户群体。GUI 不是 power-user 的需求，是**降低入门门槛**的需求。

---

## 2. 用户画像

| 画像 | 场景 | 对 GUI 的真实需求 |
|------|------|------------------|
| P1 专业渗透测试工程师 | Kali VM，engagement 2-4 周 | **中**（dashboard 看全局，执行还是 CLI） |
| P2 CTF 选手 | HTB/THM 单 box 突击 | **低**（速度第一，CLI 够用） |
| P3 SOC/蓝队分析师 | 用攻击工具做防御评估 | **高**（不想学命令行语法） |
| P4 安全培训学员 | 课堂演练 | **极高**（引导式流程） |
| P5 Bug bounty hunter | 个人长时间跟目标 | **中**（findings 表 + 截图管理） |
| P6 客户 / 管理层 | 看报告、看进度 | **极高**（只看，不操作） |
| P7 红队主管 | 看全队 engagement 状态 | **极高**（仪表盘、工时、证据链） |

**结论**:
- 仅服务 P1 + P2 → 不需要 GUI
- 覆盖 P3 + P4 + P6 + P7 → **GUI 必要**
- P6（客户）需要的是**导出报告**而非完整 GUI（不拥有 engagement）

---

## 3. 7 个技术选项

### 选项 A — Tauri 桌面应用

典型: **Caido**、Obsidian、GitButler。

**技术栈**: Rust + Webview (Safari on macOS, WebView2 on Win, WebKitGTK on Linux)
**前端框架**: 任意（React / Vue / Svelte）

**优点**:
- 单个 ~10MB 二进制（比 Electron 的 ~150MB 小 15 倍）
- 性能好、内存占用低
- 能访问文件系统 / OS API

**缺点**:
- 跨平台打包麻烦（每个 OS 要签名）
- 需要写 Rust IPC 桥接
- 更新分发复杂（auto-update 自行实现）
- 前端 + Rust + Python 三语言维护

**适用度**: ⚠️ 适合桌面工具（如 Caido 本身）。**不适合** web-first 的渗透作业。

---

### 选项 B — Local Web App（浏览器 + 后端 REST）

典型: **BloodHound CE**、**Havoc Web Client**、**Faraday**、**DefectDojo**。

**技术栈**:
- 后端: FastAPI + SQLAlchemy + WebSocket
- 前端路线选择（见 §9）

**优点**:
- 跨平台 100% 免费（任何有浏览器的系统）
- 易共享（团队 SSH 转发就能远程用）
- 更新分发 = git pull + pip install
- 复用已有的 Python 后端生态

**缺点**:
- 需要启一个 server 进程（占端口）
- 浏览器安全策略（CORS / file://）偶尔烦人
- 不如 native 快

**适用度**: ✅ **最适合**。渗透作业本质是数据管理 + 流程执行，web 天然合适。

---

### 选项 C — Terminal UI（TUI）

典型: **lazygit**、**k9s**、**btop**、**crackmapexec** 的 --cli mode。

**技术栈**: Python Textual（由 Rich 作者 Will McGugan 维护）或 Rust ratatui。

**优点**:
- 极轻量（50KB 代码）
- SSH 远程无痛（所有渗透 VM 都能跑）
- 红队文化契合（很多 operator 活在 tmux 里）
- 和现有 CLI 共生

**缺点**:
- 功能受限（不能嵌图表、图片、PDF）
- 学习曲线对非 CLI 用户陡
- 颜值一般（特殊字符依赖终端支持）

**适用度**: ✅ **补充** 用。配 Web UI 双轨。

---

### 选项 D — Streamlit / Gradio

典型: **LangChain demo**、许多 AI tool showcase。

**优点**:
- 原型极快（几小时出 demo）
- 数据可视化天然（Plotly / Altair 整合）
- Python 单文件

**缺点**:
- 不够"产品感"
- 定制 UI 难
- Streamlit 每次交互全页 rerun，性能差
- 多 user 支持弱

**适用度**: ❌ 适合内部工具 / 演示，**不适合产品**。

---

### 选项 E — Jupyter Notebook + ipywidgets

**优点**:
- 安全研究员熟悉
- 交互式探索强

**缺点**:
- 不是"应用"，是文档
- 用户需要装 JupyterLab

**适用度**: ❌ 作为独立 UI 方案不行；**但** 可以作为 "power-user recipe notebook" 额外交付（见 §8 Phase 5）。

---

### 选项 F — VS Code Extension

典型: **Continue.dev**、**GitHub Copilot**、**Cline**。

**优点**:
- IDE 里直接用（Cursor / VSCode 用户已在那）
- UI 由 VS Code 提供（Tree view / Webview / notifications）
- 打包分发走 Marketplace

**缺点**:
- 强绑 VS Code 家族
- 非 IDE 用户不能用
- Extension API 限制多（不能长期后台 server）

**适用度**: ⚠️ 作为**补充** 有价值（显示 engagement status bar 等），不能是主 UI。

---

### 选项 G — Discord/Slack/Telegram Bot

典型: **Mythic C2 的 Slack 插件**、**内部 SOC Bot**。

**优点**:
- 团队协作天然
- 移动端可用（手机看通知）

**缺点**:
- 第三方基础设施依赖
- 发敏感数据到公共平台有合规问题
- 不算 GUI

**适用度**: ❌ 不适合作为主 UI；**但** 可以作为 notification channel（engagement 结束时通知）。

---

## 4. 成本矩阵

以"单开发者 + LLM pair"为口径估算。

| 选项 | 初始开发 | 每个新 tool 增量 | 每年维护 | 用户覆盖 | 推荐度 |
|------|---------|----------------|---------|---------|--------|
| A. Tauri 桌面 | **30 人日** | 1 日 | 高 | P1/P3/P7 | 🟡 2/5 |
| B. Web App (FastAPI+htmx) | **10 人日** | 0.5 日 | 低 | 全部 P | 🟢 5/5 |
| B. Web App (FastAPI+SvelteKit) | **18 人日** | 1 日 | 中 | 全部 P | 🟢 4/5 |
| C. TUI (Textual) | **5 人日** | 0.2 日 | 低 | P1/P2 | 🟢 4/5 |
| D. Streamlit | **3 人日** | 0.3 日 | 低 | 内部 | 🔴 1/5 |
| E. Jupyter | **2 人日** | 0.1 日 | 极低 | P1 power | 🟡 2/5 |
| F. VSCode Extension | **15 人日** | 1 日 | 中 | IDE 用户 | 🟡 2/5 |
| G. Chat Bot | **5 人日** | 0.5 日 | 中 | 团队通知 | 🟡 3/5 |

**关键观察**:
- **B (Web + htmx) 初始成本 10 人日、增量 0.5 日**，是单位 ROI 最高的。
- C (TUI) 几乎白送（用同一组 REST API）。
- A (Tauri) 高门槛不合算，除非有移动互联网诉求。

---

## 5. 推荐方案

### 三层 UI 策略

```
┌───────────────────────────────────────────────────┐
│  Web Dashboard (B)       主 UI，浏览器访问        │
│    FastAPI + htmx + Tailwind + Alpine             │
├───────────────────────────────────────────────────┤
│  TUI (C)                SSH/远程场景，原生终端    │
│    Textual（共用同一 REST）                       │
├───────────────────────────────────────────────────┤
│  MCP-over-stdio (existing)  LLM agent 交互        │
└───────────────────────────────────────────────────┘
         │
         └─ 所有 UI 共用同一 core + domain DB
```

**三者服务不同场景**:
- 日常作业：Web Dashboard（最丰富）
- 跳板机 / SSH 容器：TUI
- LLM 调度：MCP（已有）

**不做** 的选项:
- Tauri 桌面（ROI 差）
- Streamlit（不是产品）
- Chat Bot 主 UI（只作通知）

### 为什么 Web + htmx 而不是 React/Svelte

**htmx + Alpine + Tailwind + Jinja2** 走 hypermedia / HTML-over-the-wire 路线：

- **无 build step** — 纯 Python 项目，不引入 node_modules
- **后端主导** — 路由/状态全在 FastAPI，前端只是 dumb render
- **维护成本** — 一个开发者能搞完；React/Svelte 需要前端专职
- **实际成功案例** — GitHub（部分）、Basecamp、Django admin、Supabase admin UI

代价:
- UI 交互丰富度不如 SPA（但对仪表盘 + 表格 + 表单足够）
- 搜索引擎上可讨论的资料少于 React

**备选**: 如果你觉得 htmx 冷门不放心，走 **SvelteKit**，成本 +8 人日。不推荐 Next.js（太重）。

---

## 6. 分层架构（后端共用）

```
┌─────────────────────────────────────────────────────────┐
│  MCP server  │  Web UI  │  TUI  │  CLI  │  Public REST │  View layer
├──────────────┴──────────┴───────┴───────┴──────────────┤
│                                                         │
│  FastAPI application (new)                              │
│   /api/v1/engagements                                   │
│   /api/v1/targets                                       │
│   /api/v1/findings                                      │
│   /api/v1/tools/invoke   (WebSocket for streaming)      │
│   /api/v1/sessions                                      │
│   /ws/events             (SSE/WS push)                  │
│                                                         │
│  All routes reuse the exact same domain services        │
│  that MCP tools call.                                   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Domain services (to build; see DOMAIN_MODEL.md)        │
│   EngagementService / TargetService / FindingService    │
│   CredentialService / ArtifactService / SessionService  │
├─────────────────────────────────────────────────────────┤
│  Tool modules  │  Plugins  │  Executors                 │  Core
└─────────────────────────────────────────────────────────┘
```

**关键约束**:
- Web UI / TUI / MCP **绝不**独自实现业务逻辑
- 全部通过 domain service 走
- 这样 UI 改动不触碰 core

---

## 7. Web Dashboard 功能清单

按优先级分层。

### Tier 1 — MVP（必须有）

**导航**:
```
◎ Engagements
  ├─ List
  └─ Detail
      ├─ Overview
      ├─ Targets
      ├─ Findings
      └─ Timeline (audit log)
◎ Tools
  └─ Launch (form-based invocation)
◎ Settings
  ├─ API keys (backends)
  └─ Tool binary paths
```

**Overview 页**:
- Active engagement summary card
- 最近 5 个 findings
- 最近 10 个 tool invocations
- Scope entries

**Findings 表**:
- 按 severity 过滤
- 按 target / tool 过滤
- 行内编辑 status（new → triaged → fixed）
- 导出 JSON / CSV

**Tool Launch**:
- 选 tool → 自动渲染表单（从 JSON Schema）
- Submit 后跳 Job 详情页
- Job 页显示实时 stdout/stderr（WebSocket）

**Audit Log**:
- 可过滤的表格
- 显示 `tool_name / actor / duration / exit_code`

### Tier 2 — 增强（第二轮）

**Reports**:
- 在线 Markdown 编辑器（Milkdown 或 CodeMirror）
- 实时预览
- Findings 表格嵌入
- 导出 PDF（Weasyprint）/ HTML / Markdown

**Credentials Vault**:
- 列表（默认脱敏）
- 点击 "Reveal" 输入 passphrase 解密
- 审计"谁何时查看"

**Sessions Monitor**:
- Sliver / Havoc sessions 实时 table
- 心跳状态图
- Quick command 面板

### Tier 3 — 可视化（第三轮）

**Attack Graph**:
- Cytoscape.js 渲染 target ↔ session ↔ credential 关系
- BloodHound-like 实用

**Network Map**:
- 当 ligolo tunnel 激活时展示拓扑

**Timeline**:
- 甘特图样的 tool invocation 时间线

---

## 8. 实施分阶段

### Phase 1 — 基础 Web MVP（5 人日）

```
[Day 1] FastAPI 应用骨架 + SQLAlchemy ORM
        domain service 最小集: Engagement / Finding / Target
[Day 2] Jinja templates: layout + engagement list / detail
        htmx + Tailwind 基础
[Day 3] Findings 表格 + 过滤 + 行内编辑
        Tool Launch 表单自动从 JSON Schema 生成
[Day 4] WebSocket 实时 stdout 流
        Settings 页面
[Day 5] CLI 命令: kestrel-mcp web
        Docker compose one-liner
        README 更新
```

**交付**:
- 浏览器打开 `http://localhost:8765` 能用
- 和 MCP 共用一个 `~/.kestrel/engagements/<name>.db`
- LLM 在 Cursor 里改数据，Web 刷新就看到

### Phase 2 — 实时性 + 报告（5 人日）

```
[Day 6] Audit Log 页面 + WebSocket 全局事件 bus
[Day 7] Job queue page: 并行 jobs 进度条
[Day 8] Markdown 编辑器 (Milkdown) + Findings 插入
[Day 9] PDF 导出 (Weasyprint)
[Day 10] 打磨：icons / shortcuts / 空态
```

### Phase 3 — TUI（3 人日）

```
[Day 11] Textual 骨架 + Engagement list view
[Day 12] Findings view + Sessions view
[Day 13] kestrel-mcp tui 命令 + 文档
```

### Phase 4 — 可视化（5 人日，可选）

```
Cytoscape 攻击图
Timeline 甘特图
Network topology when tunnels active
```

### Phase 5 — 补充（按需）

- VS Code Extension（status bar + tree view）
- Jupyter notebook cookbook
- Telegram bot for notifications

**累计到 Phase 3 = 13 人日 ≈ 2 周 pair**。

---

## 9. 技术栈细节

### 后端

```toml
# 新增依赖（附加到 pyproject.toml）
fastapi = "^0.115"
uvicorn[standard] = "^0.32"    # 含 websocket
sqlalchemy = "^2.0"
alembic = "^1.14"
jinja2 = "^3.1"                # 已有
python-multipart = "^0.0"      # 已有（via starlette）
weasyprint = "^62"             # PDF 导出
```

### 前端（htmx 路线）

```
htmx@2.0              — hypermedia exchanges
alpinejs@3            — 轻量客户端状态
tailwindcss@3         — CSS framework (via CDN, 无 build)
hyperscript@0.9       — 声明式事件（可选，补 alpine）
```

**零 npm install**。全部 CDN 引入，纯 HTML + JS。

### 前端（SvelteKit 备选）

```
sveltekit@2
tailwindcss
@melt-ui/svelte       — headless components
tanstack-query        — data fetching
```

代价：npm 生态 + Vite build step。ROI 低于 htmx。

### TUI

```toml
textual = "^0.80"
```

Will McGugan 维护，成熟稳定，Rich + 键鼠事件 + Widget 库。

### 启动命令扩展

```bash
kestrel-mcp serve       # 现有 MCP stdio（默认）
kestrel-mcp web         # 新：启动 Web UI on :8765
kestrel-mcp tui         # 新：TUI 接管终端
kestrel-mcp api         # 新：仅 REST API 不含 UI（给外部工具用）
```

### 部署

```bash
# 本机开发
kestrel-mcp web --host 127.0.0.1 --port 8765

# 团队共享（VPN/内网）
kestrel-mcp web --host 0.0.0.0 --port 8765 --auth-required

# Docker
docker run -p 8765:8765 -v ~/.kestrel:/data ghcr.io/xxx/kestrel-mcp web
```

---

## 10. 风险与 trade-off

### 风险 R-1 — 数据模型还没定，UI 先走会返工

**对策**: UI 开发强依赖 DOMAIN_MODEL.md。**先定 domain model，再开工 UI**。
不然 Phase 1 Day 1 做的 `EngagementService` 会和后来的 schema 冲突。

**顺序**:
```
1. 先做 GAP_ANALYSIS 的 P0（domain model）
2. 再做 UI Phase 1
```

### 风险 R-2 — 多 UI 测试成本

每加一个 UI 层（Web / TUI），测试 matrix 就翻一倍。

**对策**: REST API 是单一 source of truth；UI 只做 thin client；
主要 test 都在 domain service 层。UI 侧只测 smoke（能打开、能点击、能提交）。

### 风险 R-3 — Web UI 的 authZ/authN

本地单用户：不需要登录。
团队共享：需要 auth。简单方案：basic auth + HTTPS。复杂方案：OIDC（等有需求再做）。

**对策**: Phase 1 只做 `127.0.0.1` 绑定，不支持远程。
Phase 2 起加 `--auth-required` + HTTP Basic。

### 风险 R-4 — CVE 面变大

Web app 增加攻击面（CSRF / XSS / auth bypass）。我们又是安全工具，讽刺得很。

**对策**:
- 默认 127.0.0.1 绑定
- 无 public-facing 默认配置
- FastAPI 的自动 Pydantic validation 基本堵住 XSS
- CSRF: 用 SameSite=Strict cookie
- 加入威胁模型（THREAT_MODEL.md 补一章）

### 风险 R-5 — 前端技术路线长期锁定

htmx 是赌"hypermedia 卷土重来"。如果五年后 htmx 凉了？

**对策**:
- 后端 REST API 不依赖任何 UI，换前端不动后端
- htmx 学习曲线低，换 Svelte/React 重写 template 是几天工作

### Trade-off 总结

| 维度 | htmx 路线 | Svelte 路线 | Tauri 路线 |
|------|----------|-------------|-----------|
| 初始成本 | ✅ 低 | 🟡 中 | ❌ 高 |
| 维护成本 | ✅ 低 | 🟡 中 | ❌ 高 |
| UI 丰富度 | 🟡 中 | ✅ 高 | ✅ 高 |
| 性能 | ✅ 好 | ✅ 好 | ✅ 最好 |
| 分发 | ✅ 开箱即用 | 🟡 需 build | ❌ 复杂 |
| 前端生态 | 🟡 小 | ✅ 大 | ✅ 大 |
| 团队技能匹配 | ✅ Python-only | 🟡 要学前端 | ❌ 要学 Rust + 前端 |

---

## 11. 等你决策的 4 件事

在动工 Phase 1 前，我需要你定：

### D-1 — UI 层组合

```
[ ] A. 仅 MCP（当前状态，不加 UI）
[ ] B. MCP + Web Dashboard
[ ] C. MCP + Web Dashboard + TUI  ← 我推荐
[ ] D. MCP + TUI only（无 Web）
[ ] E. MCP + Tauri 桌面
```

### D-2 — Web 前端技术栈（如果选 B/C）

```
[ ] A. htmx + Alpine + Tailwind（我推荐，无 build step）
[ ] B. SvelteKit + Tailwind（前端丰富，+8 人日）
[ ] C. Vue 3 + Element Plus（中文文档多）
[ ] D. React + shadcn/ui（生态最大，+10 人日）
```

### D-3 — 首发功能范围

```
[ ] A. Tier 1 only（engagement CRUD + findings + tool launch）
[ ] B. Tier 1 + 2（加 reports + credentials vault）
[ ] C. Tier 1 + 2 + 3（加可视化攻击图）
```

Tier 1 = 5 人日。Tier 1+2 = 10 人日。全都做 = 15 人日。

### D-4 — 实施顺序

```
[ ] A. UI 优先：先做 UI，domain model 边做边磨
[ ] B. Domain first：按 GAP_ANALYSIS 先做 P0（domain model），再上 UI
     ← 我推荐（避免 UI 返工）
```

---

## 12. 下一步动作

你回复 4 个决策后，我立即执行对应路径。

**推荐答案**（如果你懒得想）:
```
D-1: C
D-2: A
D-3: A
D-4: B
```

这条路径 = **先做 domain model（~3 天）+ Web Dashboard Tier 1（~5 天）+ TUI（~3 天）** ≈ **11 天 pair**。

---

## 13. 附录 — 技术决策记录（建议未来写为 ADR）

- ADR-0010: 多 UI 层 over 单 UI（Web + TUI + MCP）
- ADR-0011: htmx over SPA 框架
- ADR-0012: FastAPI 与 MCP server 共存于同一 Python 包
- ADR-0013: domain service 层作为 UI 和 MCP 的 single source of truth

---

## 14. 相关文档

- [MASTER_PLAN.md](./MASTER_PLAN.md) — 蓝图
- [GAP_ANALYSIS.md](./GAP_ANALYSIS.md) — P0 中 domain model 是 UI 的前置
- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) — UI 要绑的实体
- [DEVELOPMENT_HANDBOOK.md](./DEVELOPMENT_HANDBOOK.md) — 代码规范通用
- [THREAT_MODEL.md](./THREAT_MODEL.md) — UI 加入后 threat surface 变化
