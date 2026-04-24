---
id: RFC-002
title: GitHub Actions CI matrix
epic: A-Foundations
status: open
owner: unassigned
role: backend-engineer
blocking_on:
  - RFC-001
budget:
  max_files_touched: 5
  max_new_files: 4
  max_lines_added: 250
  max_minutes_human: 20
  max_tokens_model: 12000
files_to_read:
  - pyproject.toml
  - uv.lock
  - scripts/full_verify.py
files_will_touch:
  - .github/workflows/ci.yml       # new
  - .github/workflows/codeql.yml   # new
  - .github/dependabot.yml         # new
  - .github/pull_request_template.md  # new
  - CHANGELOG.md                   # modified
verify_cmd: |
  .venv\Scripts\python.exe -c "import yaml, pathlib, sys; [yaml.safe_load(p.read_text('utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('ok')"
rollback_cmd: |
  git checkout -- CHANGELOG.md
  if exist .github\workflows\ci.yml del .github\workflows\ci.yml
  if exist .github\workflows\codeql.yml del .github\workflows\codeql.yml
  if exist .github\dependabot.yml del .github\dependabot.yml
  if exist .github\pull_request_template.md del .github\pull_request_template.md
skill_id: rfc-002-github-ci
---

# RFC-002 — GitHub Actions CI matrix

## Mission

搭 CI：每个 PR 自动跑 lint + matrix test + security scan，PR 模板强制填清单。

## Context

- AUDIT D-8 指出当前完全没有 CI。
- 三平台三 Python 版本手测不现实。
- RFC-003+ 后所有 PR 必须先绿 CI 再允许 review。
- 本 RFC 不配置 GitHub 侧的 branch protection（那是 repo admin 的事），只负责 workflow 文件本身。

## Non-goals

- 不做 release pipeline（留给 RFC-H02）
- 不做 Docker image 构建（同上）
- 不启用 pre-commit hooks（留给未来 RFC）
- 不配置签名 commit（OpenSSF scorecard 路线，晚点做）

## Design

3 个 workflow：

1. `ci.yml` — PR 和 push 触发。先 lint（ubuntu + py3.12 一次）；过了才 fan-out 跑 3 OS × 3 Python 的测试矩阵。
2. `codeql.yml` — 每周一 UTC 00:00 + push to main 触发。
3. `dependabot.yml` — 每周自动 PR 升级依赖。

Lint 用 **ruff**（一条工具搞定 format + lint），**mypy** 用 `--strict` 但暂时只跑 `src/redteam_mcp/core` 和 `src/redteam_mcp/domain`（避免现有未类型化的 tools 文件拖 red）。

Tests 跑两轮：

1. `pytest tests/` — 单元 + 集成
2. `scripts/full_verify.py` — 端到端 8 项

PR 模板用 DEVELOPMENT_HANDBOOK.md §5 的格式。

## Steps

### Step 1 — ci.yml

```
WRITE .github/workflows/ci.yml
```
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        run: pip install "uv>=0.5"

      - name: Install project with dev extras
        run: uv sync --frozen

      - name: Ruff lint
        run: uv run ruff check src/ tests/

      - name: Ruff format check
        run: uv run ruff format --check src/ tests/

      - name: Mypy (core + domain)
        run: uv run mypy --strict src/redteam_mcp/core src/redteam_mcp/domain

  test:
    needs: lint
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}

      - name: Install uv
        run: pip install "uv>=0.5"

      - name: Install (frozen)
        run: uv sync --frozen

      - name: Timezone fixture (Windows needs tzdata)
        if: runner.os == 'Windows'
        run: uv pip install tzdata

      - name: Unit + integration tests
        run: uv run pytest tests/ -q --maxfail=3

      - name: Full verify (end-to-end)
        run: uv run python scripts/full_verify.py
```

### Step 2 — codeql.yml

```
WRITE .github/workflows/codeql.yml
```
```yaml
name: CodeQL

on:
  push:
    branches: [main]
  schedule:
    - cron: "0 0 * * 1"

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      actions: read
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python
      - uses: github/codeql-action/analyze@v3
```

### Step 3 — dependabot.yml

```
WRITE .github/dependabot.yml
```
```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    groups:
      patch:
        update-types: [patch]
      minor:
        update-types: [minor]

  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
```

### Step 4 — PR 模板

```
WRITE .github/pull_request_template.md
```
```markdown
## What

<!-- Short description. Link the RFC. -->

Closes: RFC-___

## Checklist (from DEVELOPMENT_HANDBOOK §5)

- [ ] `git diff --stat` matches the RFC's `files_will_touch`
- [ ] `verify_cmd` passes locally
- [ ] `scripts/full_verify.py` passes locally
- [ ] Unit tests added for new code (≥80% line coverage)
- [ ] CHANGELOG.md `[Unreleased]` updated
- [ ] THREAT_MODEL.md / GAP_ANALYSIS.md updated if this RFC closes an item
- [ ] No new dependency without `pyproject.toml` bump + `uv lock`

## How to test

<!-- Copy-pasteable commands a reviewer can run. -->

```bash
uv sync --frozen
uv run pytest tests/ -q
uv run python scripts/full_verify.py
```
```

### Step 5 — CHANGELOG 标记

```
APPEND CHANGELOG.md

- RFC-002 — GitHub Actions CI matrix (lint + 3OS×3Py tests + CodeQL)
```

（如果 CHANGELOG.md 尚未有 `[Unreleased]` 段，先创建。见 Notes）

### Step 6 — 验证 YAML 语法

```
RUN .venv\Scripts\python.exe -c "import yaml, pathlib; [yaml.safe_load(p.read_text('utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('yaml ok')"
```

### Step 7 — full_verify 回归

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

本 RFC 不引入 Python 单测（纯 CI 配置）。CI 本身就是测试（会在 PR 触发时生效）。

## Post-checks

- [ ] `.github/workflows/` 有 2 个 yml
- [ ] `.github/dependabot.yml` 存在
- [ ] `.github/pull_request_template.md` 存在
- [ ] 所有 yml 通过 pyyaml.safe_load（Step 6 已验证）
- [ ] 本地 `ruff check src/ tests/` 返回 0（用 CI 同版本）
- [ ] 下一次推送到 GitHub 时自动触发 CI，实测观察

## Rollback plan

见 front-matter `rollback_cmd`。

## Updates to other docs

- `CHANGELOG.md` [Unreleased] 加 RFC-002 条目
- `AUDIT.md` D-8 小节改成 `RESOLVED by RFC-002`
- `DEVELOPMENT_HANDBOOK.md` §14 (CI) 补一行引用到本 RFC

## Notes for executor

- 如果 CHANGELOG.md 不存在或没有 `[Unreleased]` 段，step 5 之前先 WRITE 一个空模板：
  ```
  WRITE CHANGELOG.md
  # Changelog

  All notable changes to this project will be documented here.
  The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

  ## [Unreleased]

  ### Added
  ```
- `mypy --strict` 只跑 `core` 和 `domain`。如果模型想扩大范围，拒绝 —— 那是另一个 RFC 的事（RFC-B01）。
- Windows 跑 tests 前必须 `uv pip install tzdata`，否则 alembic 会失败（AUDIT D-5 已知问题）。

## Changelog

- **2026-04-21 初版**
