# AGENT EXECUTION PROTOCOL

> 任何 agent（人/Claude/GPT-4/Qwen-7B/本地 Llama）执行 RFC 都必须遵守这份协议。
> 本协议由 [AGENT_RESEARCH.md](./AGENT_RESEARCH.md) 归纳的 7 条硬规则 + 业界最佳实践组成。
> 违反协议导致的故障由 **执行者** 承担（回滚代价）；协议本身由 **RFC 作者** 维护正确性。

**Version**: 1.0
**Last changed**: 2026-04-21

---

## 1. 三方契约（Spec Author / Executor / Reviewer）

```
┌──────────────────┐   produces   ┌───────────────┐   executes   ┌──────────────┐
│ Spec Author      │─────────────▶│   RFC (md)    │─────────────▶│   Executor   │
│ (strong model +  │              │  + verify_cmd │              │ (any model)  │
│  human review)   │              │  + tests      │              └──────┬───────┘
└──────────────────┘              └───────────────┘                     │
                                         ▲                              │
                                         │                              │
                                         │              reports result  │
                                         │                              │
                                  ┌──────┴───────┐                      │
                                  │   Reviewer   │◀─────────────────────┘
                                  │ (human)      │
                                  └──────────────┘
```

Roles:

| Role | Responsibility | Allowed tools |
|------|---------------|---------------|
| Spec Author | 写 RFC；保证 verify_cmd 在空仓库里也能编绿 | 任意 |
| Executor | 跑 RFC 的 steps；不 self-correct | 见 §6 白名单 |
| Reviewer | 跑 `verify_cmd`；合并 PR 前手工抽样 | 任意 |

**关键约束**：一个 RFC 提交时必须附带「空仓库从头执行都能通过」的证据。

---

## 2. RFC 的机器可读 front-matter

每个 `rfcs/RFC-NNN-<slug>.md` 开头必须是 YAML：

```yaml
---
id: RFC-007
title: FastAPI app skeleton
epic: C-WebUI-Tier1
status: open                # open | in_progress | blocked | done | abandoned
owner: alice                # human or agent id
role: backend-engineer      # backend / frontend / integration / test-writer / docs
blocking_on:
  - RFC-001                 # hard deps
  - RFC-002
budget:
  max_files_touched: 8
  max_new_files: 6
  max_lines_added: 800
  max_minutes_human: 20
  max_tokens_model: 40000
files_to_read:              # executor MUST NOT read others
  - src/redteam_mcp/core/services.py
  - src/redteam_mcp/core/context.py
files_will_touch:           # exact list; executor MUST NOT touch others
  - src/redteam_mcp/webui/__init__.py       # new
  - src/redteam_mcp/webui/app.py            # new
  - pyproject.toml                          # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/webui/test_app_skeleton.py -q
rollback_cmd: |
  git checkout -- .
skill_id: rfc-007-fastapi-skeleton
---
```

Fields are required unless marked optional. Any missing required field = RFC rejected by reviewer.

---

## 3. RFC 的人类可读 body（必备小节）

按顺序：

1. **Mission** — 一句话，不超过 30 字。
2. **Context** — 3-5 bullet 说明为什么做这个。
3. **Non-goals** — 明确不在本 RFC 范围的事，防止 scope creep。
4. **Design** — 选定的实现方案（不是方案 A/B/C 讨论）。
5. **Steps** — 编号的原子步骤，每步带 action + verification。
6. **Tests** — 内嵌的测试代码 / 预期结果。
7. **Post-checks** — 除了 `verify_cmd`，还要人眼看一眼的 smoke。
8. **Rollback plan** — 一旦 verify_cmd 失败如何回到出发点。
9. **Updates to other docs** — 哪些 md 要同步更新。

---

## 4. Step 指令语法

RFC 的 steps 只能用下面 4 种指令（Aider 式）。弱模型只认这 4 种，其他写法视为「说明文字」被忽略。

### 4.1 `WRITE <path>`

创建 / 完全覆盖文件。

````
WRITE src/redteam_mcp/webui/app.py
```python
from __future__ import annotations
...
```
````

### 4.2 `REPLACE <path>`

原子替换。SEARCH 块必须在目标文件里唯一匹配；否则失败，不得「重试更大片段」。

````
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
        self.modules = load_modules(settings, self.scope_guard)
=======
        self.modules = load_modules(settings, self.scope_guard)
        self.webui_mount: Any | None = None
>>>>>>> REPLACE
````

### 4.3 `APPEND <path>`

在文件末尾追加（给 `__init__.py` / `CHANGELOG.md` 用）。

````
APPEND src/redteam_mcp/webui/__init__.py
from .app import create_app

__all__ = ["create_app"]
````

### 4.4 `RUN <shell-command>`

运行一条 shell 命令。命令必须在 §6 白名单内，否则拒绝。

````
RUN .venv\Scripts\python.exe -m pytest tests/unit/webui/ -q
````

**禁止** 组合指令（`cd x && make`）；一条 RUN 只做一件事。

---

## 5. 验证规则

### 5.0 `validate_rfc.py` 预检（**2026-04-21 强制加入**）

在 Steps 开始**之前**，执行者必须跑：

```
RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-<id>-*.md
```

**exit code 0**：spec 结构健康，可以进 §5.1。
**exit code 非 0**：spec 本身有缺陷（phantom paths / 不匹配 SEARCH / budget
超限 / RUN 非白名单）。**立刻停止**，在 RFC 里写 `status: blocked` 并标
`reason: spec_failed_preflight`，不要试图在执行中"修 spec"。

本步骤来源：2026-04-21 审计发现 15 个 full-fleshed RFC 中 10 个 pre-flight
失败（RFC_AUDIT_PREFLIGHT.md）。通过机器检测，80% 的 spec 缺陷能在执行前
拦住。

### 5.1 `verify_cmd` 运行协议

执行者在所有 `steps` 跑完后必须执行且仅执行 `verify_cmd`，不带任何修改。

```
exit code 0  →  task = done, proceed to §8 PR checklist
exit code ≠ 0 → go to §5.2 retry policy
```

### 5.2 Retry policy

最多尝试 3 次，每次之间不得 self-correct：

```
Attempt 1: 执行 steps 一次 → verify
Attempt 2: 如果 verify 失败，git checkout -- . 然后重新跑 steps
Attempt 3: 同上
```

如果 3 次都红：

1. 执行 `rollback_cmd`
2. 在 RFC 文件顶部写入 `status: blocked` + 简短原因
3. 停止，让 Reviewer 介入

**禁止** 临时修改 `verify_cmd` 让它绿。那叫「作弊」。

### 5.3 最终回归

每个 RFC 的最后一步固定是：

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

如果之前的 `verify_cmd` 绿但 `full_verify.py` 红，说明 RFC 破坏了既有功能 → 必须修到两者都绿。

---

## 6. Executor 工具白名单

弱模型在执行 RFC 时只能用：

| 工具 | 用途 | 限制 |
|------|-----|------|
| `Read` | 读 `files_to_read` 列表里的文件 | 不得读其他文件 |
| `WRITE` / `REPLACE` / `APPEND` | 编辑 `files_will_touch` 里的文件 | 不得编辑其他 |
| `RUN` | 跑命令 | 只允许白名单 |
| `TodoWrite` | 标记 step 进度 | 不得改 RFC 本身 |

**白名单 RUN 命令前缀**：

```
.venv\Scripts\python.exe
.venv\Scripts\pytest.exe
.venv\Scripts\ruff.exe
.venv\Scripts\mypy.exe
.venv\Scripts\alembic.exe
git status
git diff
git checkout -- .
```

**禁止**：
- `curl` / `wget` / `pip install` （依赖变更走 pyproject.toml，由 RFC-002 CI 装）
- 自由的 `find` / `grep` / `Get-ChildItem -Recurse`
- 任何写入 `~/.cursor/` 或 `$env:USERPROFILE` 之外路径的命令

---

## 7. Budget 强制

RFC front-matter 的 `budget` 字段定义硬上限：

| 字段 | 超过时行为 |
|------|-----------|
| `max_files_touched` | 立即停止，status=blocked，原因=budget_exceeded |
| `max_new_files` | 同上 |
| `max_lines_added` | 同上 |
| `max_minutes_human` | 人类评审员可以强制停止 |
| `max_tokens_model` | 跑到的模型自行报告超额；可以继续但计入风险 |

预算超过不是失败，是信号：**RFC 写得太大，应该拆分**。

---

## 8. PR checklist（Reviewer 用）

Reviewer 合并前逐项打勾：

```
[ ] git diff --stat 仅包含 files_will_touch 里的文件
[ ] verify_cmd 本机跑绿
[ ] scripts/full_verify.py 本机跑绿
[ ] 新增/修改测试在 PR 里可见
[ ] THREAT_MODEL.md / GAP_ANALYSIS.md 如提到本 RFC 要关闭的威胁/gap，状态已更新
[ ] CHANGELOG.md 的 [Unreleased] 段已加条目
[ ] RFC 文件 status=done
[ ] 下一个解锁的 RFC 已从 INDEX.md 的 blocked 列表移除
```

---

## 9. Skills 层集成

每个 RFC 对应一个 Cursor skill，skill 内容极简：「读这份 RFC，按协议执行」。

**skill 文件命名**：`.cursor/skills-cursor/rfc-runner/<rfc-id>/SKILL.md`

**skill 触发词**：`execute RFC-NNN` / `run RFC-NNN` / `做 RFC-NNN`

**skill body 模板**（所有 skill 复用）：

```markdown
---
name: rfc-runner-<id>
description: Execute <RFC-id> <title> per AGENT_EXECUTION_PROTOCOL. Use when the user says "run RFC-XXX" / "execute RFC-XXX" / "做 RFC-XXX".
---

# RFC Runner — <RFC-id>

1. Read `rfcs/RFC-<id>-*.md`.
2. Read only files in `files_to_read`.
3. Execute `steps` using WRITE/REPLACE/APPEND/RUN indicators.
4. Run `verify_cmd`. If red, follow retry policy.
5. Run `scripts/full_verify.py`.
6. If green: update RFC status to `done`, commit with message `RFC-<id>: <title>`.
7. If red after 3 attempts: status=blocked, stop.

No exploration. No self-correction beyond 3 retries. No scope creep.
```

这样即使弱模型也能「抬手就跑」，因为 skill 的逻辑是固定的，模型只要不偏题就行。

---

## 10. 错误上报格式

如果 RFC blocked，执行者必须在 RFC 文件末尾追加：

```yaml
---
blocked_at: 2026-04-21T12:34:56Z
blocked_at_step: 5
reason: verify_cmd exit 1
last_stderr_tail: |
  FAILED tests/unit/webui/test_app_skeleton.py::test_create_app - ImportError: cannot import name 'X' from 'Y'
attempts: 3
```

Reviewer 读这段就知道失败在哪，不用重跑。

---

## 11. 进度跟踪

本仓库根级 `rfcs/INDEX.md` 维护所有 RFC 的状态表。任何 RFC 状态变化必须同步 INDEX：

```
| id      | status      | blocking_on | owner |
|---------|-------------|-------------|-------|
| RFC-001 | done        |             | alice |
| RFC-002 | in_progress | RFC-001     | bob   |
| RFC-003 | open        | RFC-001     |       |
| RFC-004 | blocked     | RFC-002     | alice |
```

---

## 12. Glossary

- **Executor** — 拿到 RFC 并运行它的实体。可以是人、Claude、GPT-4、Qwen-7B。
- **Spec Author** — 写 RFC 的人。不等同于 Executor。
- **Reviewer** — 合并 PR 的人。必须是人类（不是 agent）。
- **atomic step** — 一条 WRITE/REPLACE/APPEND/RUN 指令。
- **verify_cmd** — 一条 shell 命令，退出码 0 算成功。
- **budget** — 硬预算，超过即 RFC 拆分。
- **skill** — Cursor 里的 SKILL.md 文件，用自然语言触发 RFC 执行。

---

## 13. 版本记录

- **1.0 (2026-04-21)** — 初版。基于 AGENT_RESEARCH.md 的 10 条模式 + 本项目已知坑。
