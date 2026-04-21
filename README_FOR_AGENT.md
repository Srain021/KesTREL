# README FOR AGENT

> **先读这个。** 无论你是 Claude Opus 还是 Qwen-7B，打开这个项目第一件事就是读本文档。
> 读完 2-3 分钟就能开工。

---

## 1. 你在哪 / 这是什么

- 项目: **kestrel-mcp**（当前 package 名 `kestrel_mcp`，待 RFC-H01 改名）
- 路径: `d:\TG PROJECT\kestrel-mcp\`
- Python venv: `d:\TG PROJECT\kestrel-mcp\.venv\`
- 用途: MCP 服务器，把 7+ 个进攻性安全工具暴露给 LLM

## 2. 你要做什么

**你不自由发挥。你按 RFC 执行任务。**

每个具体任务都写在 `rfcs/RFC-<NNN>-<slug>.md` 里，含：

- Mission（要做什么）
- `files_to_read` / `files_will_touch`（允许动的文件）
- `Steps`（WRITE / REPLACE / APPEND / RUN 指令序列）
- `verify_cmd`（唯一的成功判据）
- `rollback_cmd`（失败回滚）
- `budget`（硬预算）

**工作流**：

1. 用户说「做 RFC-007」
2. 你读 `rfcs/RFC-007-*.md`
3. 你读 `files_to_read` 里列的文件（**只能读这些**）
4. 你按 `Steps` 执行（**只改 `files_will_touch` 里的文件**）
5. 你跑 `verify_cmd`
6. 你跑 `scripts/full_verify.py` 确保没破坏其他东西
7. 你更新 RFC status + CHANGELOG + commit

## 3. 硬规则（违反立刻停下）

见 [AGENT_EXECUTION_PROTOCOL.md](./AGENT_EXECUTION_PROTOCOL.md) §2-§7 的完整列表。最重要的 5 条：

1. **只读 RFC 的 `files_to_read` 列表**。不 grep，不自由浏览。
2. **只改 RFC 的 `files_will_touch` 列表**。
3. **WRITE/REPLACE/APPEND/RUN 之外的话都是文档**，不要执行。
4. **Verify 失败最多重试 3 次**。之后 rollback + status=blocked + stop。
5. **不碰 `verify_cmd`**。它是标尺，你不能为了通过修改标尺。

## 4. 读取顺序（每次会话开始）

```
1. README_FOR_AGENT.md   ← 本文件
2. AUDIT.md              ← 知道哪些地方已经坏了 / 脆弱
3. AGENT_EXECUTION_PROTOCOL.md  ← 执行硬契约
4. rfcs/INDEX.md         ← 知道有哪些 RFC、依赖关系
5. <目标 RFC>.md         ← 执行目标
```

其他文档（DOMAIN_MODEL / THREAT_MODEL / MASTER_PLAN / UI_STRATEGY）**只在 RFC 的 `files_to_read` 指向它时读**。

## 5. 你能用的工具

| 工具 | 用途 | 限制 |
|------|------|------|
| Read | 读 `files_to_read` 里的文件 | 不得读其他文件 |
| Write | 创建新文件 | 只能是 `files_will_touch` 里的 |
| StrReplace | 修改既有文件 | 只能是 `files_will_touch` 里的；SEARCH 必须唯一匹配 |
| Shell / Bash | 跑 RUN 指令 | 命令必须在白名单：python / pytest / ruff / mypy / alembic / git status|diff|checkout |
| TodoWrite | 跟踪 step 进度 | 不改 RFC 文件本身 |

**禁止**：
- `curl` / `wget` / `pip install <x>`（依赖变更走 `uv lock`）
- 自由 `find` / `grep -r` / `Get-ChildItem -Recurse`
- 写到 `~/.cursor/` 或 `$env:USERPROFILE` 之外的路径

## 6. 第一次启动？

```powershell
cd "d:\TG PROJECT\kestrel-mcp"
.\.venv\Scripts\Activate.ps1

# 检查环境
.\.venv\Scripts\python.exe scripts\full_verify.py
# 应输出：Result: 8/8 checks passed.
```

如果不是 8/8，说明代码库当前坏的；**先别做新 RFC**，去修（这本身应该是某个 RFC 的范围）。

## 7. 不知道下一步？

对用户说「下一步做什么」或 Cursor skill `kestrel-mcp-what-to-do-next` 会帮你：

- 扫 `rfcs/INDEX.md`
- 挑出所有 blocker 都 done 的 RFC
- 按 Epic A → H 顺序给你前 3 个

## 8. 失败怎么办

不要瞎试。按顺序：

1. 运行 `git diff --stat` — 确认你改的文件在 `files_will_touch` 里
2. 重新看 RFC 的 `Steps` — 有没有漏一步
3. 看 verify_cmd 的 stderr tail — 通常是 import 错或测试未覆盖
4. **最多重试 3 次**
5. 3 次都失败：
   - `git checkout -- .`（或 RFC 的 `rollback_cmd`）
   - 给用户一个 2-行报告：哪步失败、stderr tail、已 rollback
   - 停止

## 9. 成功的样子

- 所有 Steps 都跑完没报错
- `verify_cmd` exit 0
- `full_verify.py` 显示 `Result: 8/8 checks passed.`
- `git diff --stat` 只包含 `files_will_touch`
- RFC 文件 status=done
- CHANGELOG.md 的 `[Unreleased]` 有一行新条目
- commit message: `RFC-<id>: <title>`

## 10. 版本

- 本 README 版本: 1.0 / 2026-04-21
- 一致的协议版本: AGENT_EXECUTION_PROTOCOL.md 1.0

---

## 快捷导航

| 想做 | 读哪个 |
|------|-------|
| 了解全局 | [README.md](./README.md) |
| 诚实现状 | [AUDIT.md](./AUDIT.md) |
| 执行硬契约 | [AGENT_EXECUTION_PROTOCOL.md](./AGENT_EXECUTION_PROTOCOL.md) |
| 研究背景 | [AGENT_RESEARCH.md](./AGENT_RESEARCH.md) |
| 业务建模 | [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) |
| 安全威胁 | [THREAT_MODEL.md](./THREAT_MODEL.md) |
| UI 路线 | [UI_STRATEGY.md](./UI_STRATEGY.md) |
| 蓝图 | [MASTER_PLAN.md](./MASTER_PLAN.md) |
| 开发规范 | [DEVELOPMENT_HANDBOOK.md](./DEVELOPMENT_HANDBOOK.md) |
| 工程缺陷 | [GAP_ANALYSIS.md](./GAP_ANALYSIS.md) |
| 工具矩阵 | [TOOLS_MATRIX.md](./TOOLS_MATRIX.md) |
| LLM 用工具指南 | [LLM_GUIDANCE.md](./LLM_GUIDANCE.md) |
| RFC 清单 | [rfcs/INDEX.md](./rfcs/INDEX.md) |
| RFC 模板 | [rfcs/RFC-000-TEMPLATE.md](./rfcs/RFC-000-TEMPLATE.md) |
| Skills 集成 | [SKILLS_INTEGRATION.md](./SKILLS_INTEGRATION.md) |
