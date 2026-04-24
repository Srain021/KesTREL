---
id: RFC-NNN
title: <short title, imperative voice>
epic: <EpicLetter-Name>
status: open
owner: unassigned
role: backend-engineer
blocking_on: []
budget:
  max_files_touched: 0
  max_new_files: 0
  max_lines_added: 0
  max_minutes_human: 0
  max_tokens_model: 0
files_to_read: []
files_will_touch: []
verify_cmd: |
  .venv\Scripts\python.exe scripts\full_verify.py
rollback_cmd: |
  git checkout -- .
skill_id: rfc-nnn-<slug>
---

# RFC-NNN — <title>

## Mission

<one sentence, imperative, ≤ 30 Chinese chars 或 20 English words>

## Context

- 为什么做这个（business / technical reason）
- 解决哪个已知 GAP / threat / USER_STORY
- 上游依赖的 RFC 带来的什么能力

## Non-goals

- 明确不做的事
- 留给未来 RFC 的事

## Design

<选定方案。不讨论 A/B/C，只写「我们选了 X 因为…」>

## Steps

### Step 1 — <what this step does>

<可选的 1-2 行解释>

```
WRITE path/to/new_file.py
<content>
```

或

```
REPLACE path/to/existing.py
<<<<<<< SEARCH
old
=======
new
>>>>>>> REPLACE
```

或

```
RUN .venv\Scripts\python.exe -m pytest tests/...
```

### Step 2 — ...

...

## Tests

<内嵌要添加的测试代码；或者说「沿用 step N 里的 WRITE」>

## Post-checks

除了 `verify_cmd`，人眼要看的 smoke：

- [ ] `git diff --stat` 只列出 `files_will_touch`
- [ ] ... 其他 visual check

## Rollback plan

`git checkout -- .`；如果有 db 副作用，加 `alembic downgrade -1` 等命令。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加一行「RFC-NNN closes …」
- 如果关闭 THREAT_MODEL 的某个威胁：改其 status
- 如果关闭 GAP_ANALYSIS 的某个 gap：划掉并注明 RFC

## Notes for executor (optional)

<可放一些弱模型容易搞错的提示；避免写长篇>

## Changelog

- **2026-04-21 初版** by <author>
