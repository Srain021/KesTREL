---
id: RFC-T08
title: Team bootstrap command — kestrel team bootstrap --name <slug>
epic: T-TeamEdition
status: done
owner: unassigned
role: backend-engineer
blocking_on: [RFC-A04, RFC-T00]
edition: team
budget:
  max_files_touched: 8
  max_new_files: 4
  max_lines_added: 360
  max_minutes_human: 45
  max_tokens_model: 16000
files_to_read:
  - src/kestrel_mcp/__main__.py
  - src/kestrel_mcp/core/services.py
  - src/kestrel_mcp/domain/services/engagement_service.py
  - src/kestrel_mcp/domain/services/scope_service.py
  - src/kestrel_mcp/domain/entities.py
  - README.md
files_will_touch:
  - src/kestrel_mcp/team/__init__.py              # new
  - src/kestrel_mcp/team/bootstrap.py             # new
  - src/kestrel_mcp/__main__.py                   # modified
  - tests/unit/team/__init__.py                   # new
  - tests/unit/team/test_bootstrap.py             # new
  - README.md                                     # modified
  - CHANGELOG.md                                  # modified
  - rfcs/INDEX.md                                 # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/team/test_bootstrap.py -v
rollback_cmd: |
  git checkout -- src/kestrel_mcp/__main__.py README.md CHANGELOG.md rfcs/INDEX.md
  if exist src\kestrel_mcp\team rmdir /s /q src\kestrel_mcp\team
  if exist tests\unit\team rmdir /s /q tests\unit\team
skill_id: rfc-t08-bootstrap
---

# RFC-T08 — Team bootstrap command

## Mission

`kestrel --edition team team bootstrap --name <slug> [--scope ...]` 一条命令起
队伍：建 Engagement、载默认 Scope、打印 readiness 报告。

## Context

- PRODUCT_LINES.md "最快部署能用"原则的兑现。
- RFC-A04 提供 edition + FeatureFlags；RFC-T00 提供 unleashed 行为。本 RFC 提
  供**用户入口**。
- v1 失败于 3 个 SEARCH 幻觉 + 1 个 WRITE-not-in-fwt + 错误的 `engagement.create`
  签名（v1 假设有 `description` 参数）。v2 按真实 `EngagementService.create`
  签名重写（required keyword-only: `name`, `display_name`, `engagement_type`,
  `client`）。
- v2 基于真实 `ServiceContainer.default_on_disk(*, data_dir=...)` 签名（v1
  传了位置参数）。

## Non-goals

- **不做 CTF-specific** — 不连 HTB / pull VPN / refresh nuclei templates（PRODUCT_LINES
  决策 5 明确砍）。
- 不起 docker-compose 栈（那是 deploy RFC）。
- 不集成 Vaultwarden / tmate / Obsidian vault（RFC-T01~T03 未来）。
- **不写 web UI 部分** —— 纯 CLI。
- 不实现 `session new` 这类子命令（超出本 RFC scope）。

## Design

`team bootstrap` 做 5 件事：
1. 创建 `~/.kestrel/data/` (via `ServiceContainer.default_on_disk()` 默认行为)
2. Doctor 检查关键工具（nuclei / sliver-server / caido / SHODAN_API_KEY 是否就位 ——
   缺失只 warn 不阻塞）
3. 调 `EngagementService.create(name, display_name, engagement_type, client,
   owners)` 建 Engagement，状态留在 PLANNING
4. 批量 add scope patterns via `ScopeService.add_entry(engagement_id, pattern)`
5. 打印 "Ready!" 报告 + 下一步提示

`--dry-run` 跳过 step 1-4 的副作用，只打印「会做什么」。

Typer 分组：新增 `team_app = typer.Typer(...)` + `app.add_typer(team_app,
name="team")`；`team_app.command("bootstrap")` 是本 RFC 唯一子命令。**未来
T05/T09 再加更多子命令**，不动本 RFC。

## Steps

### Step 1 — 新建 team/__init__.py 占位

```
WRITE src/kestrel_mcp/team/__init__.py
```
```python
"""Team Edition subpackage.

Only imported by CLI handlers under `kestrel team ...`. Code in this package
must check `settings.features` before invoking side effects; it MUST NOT
assume Pro safety guarantees (no rate limiting, no strict scope).

Decision log: PRODUCT_LINES.md Part 9.
"""
```

### Step 2 — 实现 bootstrap 逻辑

```
WRITE src/kestrel_mcp/team/bootstrap.py
```
```python
"""Bootstrap a crew-ready Team edition install.

Called by `kestrel team bootstrap --name <slug>`. See RFC-T08.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from kestrel_mcp.config import Settings
from kestrel_mcp.core.services import ServiceContainer
from kestrel_mcp.domain import entities as ent


@dataclass
class BootstrapReport:
    name: str
    edition: str
    data_dir: Path
    engagement_id: str | None = None
    scope_added: list[str] = field(default_factory=list)
    doctor_warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def render(self) -> str:
        lines = [
            "=" * 62,
            "  Kestrel Team Edition - Bootstrap Report",
            "=" * 62,
            f"  Engagement:    {self.name}  ({'dry-run' if self.dry_run else 'created'})",
            f"  Edition:       {self.edition}",
            f"  Data dir:      {self.data_dir}",
            f"  Engagement id: {self.engagement_id or '(would be created)'}",
            f"  Scope entries: {len(self.scope_added)}",
        ]
        for s in self.scope_added:
            lines.append(f"    - {s}")
        if self.doctor_warnings:
            lines.append("  Doctor warnings:")
            for w in self.doctor_warnings:
                lines.append(f"    ! {w}")
        lines += [
            "",
            "  Next steps:",
            f"    1. Start server:  kestrel --edition team serve",
            f"    2. Point your LLM client at the stdio transport",
            f"    3. Active engagement via env:  "
            f"$env:KESTREL_ENGAGEMENT = '{self.name}'",
            "",
            "=" * 62,
        ]
        return "\n".join(lines)


def _doctor_warnings() -> list[str]:
    warnings: list[str] = []
    for tool in ("nuclei", "sliver-server", "caido"):
        if shutil.which(tool) is None:
            warnings.append(f"{tool} not on PATH (feature degraded)")
    if not os.getenv("SHODAN_API_KEY"):
        warnings.append("SHODAN_API_KEY unset (OSINT search disabled)")
    return warnings


async def _do_bootstrap(
    settings: Settings,
    name: str,
    scope_entries: Iterable[str],
    dry_run: bool,
) -> BootstrapReport:
    # Resolve data_dir the same way ServiceContainer.default_on_disk does.
    data_dir = Path(os.environ.get("KESTREL_DATA_DIR", "~/.kestrel")).expanduser()

    report = BootstrapReport(
        name=name,
        edition=settings.edition,
        data_dir=data_dir,
        dry_run=dry_run,
        doctor_warnings=_doctor_warnings(),
        scope_added=list(scope_entries) if dry_run else [],
    )

    if dry_run:
        return report

    data_dir.mkdir(parents=True, exist_ok=True)

    container = ServiceContainer.default_on_disk(data_dir=data_dir)
    await container.initialise()
    try:
        engagement = await container.engagement.create(
            name=name,
            display_name=name.replace("-", " ").replace("_", " ").title(),
            engagement_type=ent.EngagementType.RED_TEAM,
            client="internal-crew",
            owners=[],
        )
        report.engagement_id = str(engagement.id)

        for entry in scope_entries:
            entry = entry.strip()
            if not entry:
                continue
            await container.scope.add_entry(engagement_id=engagement.id, pattern=entry)
            report.scope_added.append(entry)
    finally:
        await container.dispose()

    return report


def bootstrap(
    name: str,
    scope: str | None = None,
    dry_run: bool = False,
    edition: str | None = "team",
) -> BootstrapReport:
    """Top-level entry point. Builds Settings, runs the async core, returns
    the report dataclass.
    """

    settings = Settings.build(edition=edition)
    entries = [s.strip() for s in (scope or "").split(",") if s.strip()]
    return asyncio.run(_do_bootstrap(settings, name, entries, dry_run))
```

### Step 3 — 加 `team` 子命令组到 __main__.py

```
REPLACE src/kestrel_mcp/__main__.py
<<<<<<< SEARCH
@app.command("show-config")
def show_config_cmd() -> None:
    """Print resolved Settings (edition + features) as JSON."""

    from .config import Settings

    s = Settings.build(edition=_edition_state["value"])
    payload = {"edition": s.edition, "features": s.features.model_dump()}
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def version() -> None:
=======
@app.command("show-config")
def show_config_cmd() -> None:
    """Print resolved Settings (edition + features) as JSON."""

    from .config import Settings

    s = Settings.build(edition=_edition_state["value"])
    payload = {"edition": s.edition, "features": s.features.model_dump()}
    typer.echo(json.dumps(payload, indent=2))


team_app = typer.Typer(
    name="team",
    help="Team edition commands (use with --edition team).",
    no_args_is_help=True,
)
app.add_typer(team_app, name="team")


@team_app.command("bootstrap")
def team_bootstrap_cmd(
    name: Annotated[str, typer.Option("--name", "-n", help="Engagement slug.")],
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Comma-separated scope patterns."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview only; no DB writes."),
    ] = False,
) -> None:
    """Bootstrap a Team edition engagement in one command."""

    from .team.bootstrap import bootstrap

    edition = _edition_state.get("value") or "team"
    report = bootstrap(name=name, scope=scope, dry_run=dry_run, edition=edition)
    typer.echo(report.render())


@app.command()
def version() -> None:
>>>>>>> REPLACE
```

### Step 4 — 测试

```
WRITE tests/unit/team/__init__.py
```
```python
"""Team edition tests."""
```

```
WRITE tests/unit/team/test_bootstrap.py
```
```python
"""Tests for RFC-T08 team bootstrap command."""

from __future__ import annotations

from pathlib import Path

import pytest

from kestrel_mcp.team.bootstrap import BootstrapReport, bootstrap


def test_dry_run_reports_no_mutation(tmp_path, monkeypatch):
    # Point KESTREL_DATA_DIR at an isolated tmp so nothing real is touched.
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    report = bootstrap(name="op-test", scope="a.com,b.net", dry_run=True)

    assert report.dry_run is True
    assert report.engagement_id is None
    assert report.scope_added == ["a.com", "b.net"]
    assert report.edition == "team"
    # Dry-run must NOT create the sqlite file.
    assert not (tmp_path / "data.db").exists()


def test_report_render_contains_expected_sections():
    r = BootstrapReport(
        name="op-x",
        edition="team",
        data_dir=Path("/tmp/x"),
        dry_run=True,
        scope_added=["a.com"],
    )
    text = r.render()
    assert "Kestrel Team Edition" in text
    assert "op-x" in text
    assert "Next steps" in text
    assert "kestrel --edition team" in text
    assert "a.com" in text


def test_report_render_handles_empty_scope_and_warnings():
    r = BootstrapReport(
        name="op-y",
        edition="team",
        data_dir=Path("/tmp/y"),
        dry_run=False,
        doctor_warnings=["nuclei not on PATH"],
    )
    text = r.render()
    assert "Doctor warnings" in text
    assert "nuclei" in text


def test_real_bootstrap_creates_engagement(tmp_path, monkeypatch):
    """Non-dry-run: actually creates sqlite + Engagement."""
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("KESTREL_EDITION", raising=False)

    report = bootstrap(
        name="op-real",
        scope="example.com,target.lab",
        dry_run=False,
    )

    assert report.engagement_id is not None
    assert len(report.engagement_id) >= 32  # UUID string
    assert set(report.scope_added) == {"example.com", "target.lab"}
    # Verify sqlite file exists after.
    assert (tmp_path / "data.db").exists()


def test_empty_scope_still_creates_engagement(tmp_path, monkeypatch):
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    report = bootstrap(name="op-z", scope=None, dry_run=False)
    assert report.engagement_id is not None
    assert report.scope_added == []


def test_bootstrap_respects_pro_edition_when_forced(tmp_path, monkeypatch):
    """Sanity: if caller passes edition='pro', the report reflects pro."""
    monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))
    report = bootstrap(name="op-pro", dry_run=True, edition="pro")
    assert report.edition == "pro"
```

### Step 5 — README 加 Team Quickstart 章节

```
REPLACE README.md
<<<<<<< SEARCH
Cursor will auto-invoke `shodan_search`.

---

## 🏗️ Architecture
=======
Cursor will auto-invoke `shodan_search`.

---

## 🧑‍🤝‍🧑 Team Edition Quickstart

Team Edition is the unleashed mode for internal crews (see
[PRODUCT_LINES.md](./PRODUCT_LINES.md) Part 9). Get operational in one
command:

```powershell
# One-liner bootstrap
kestrel --edition team team bootstrap --name op-winter-2026 --scope "target.lab,*.internal"

# Then start the server, pointing your LLM client at stdio
kestrel --edition team serve
$env:KESTREL_ENGAGEMENT = "op-winter-2026"
```

What "unleashed" means in this edition:

- `scope_enforcement = warn_only` — out-of-scope targets are logged, not
  blocked (see RFC-T00).
- `rate_limit_enabled = false` — no throttling of tool calls.
- `credential_encryption_required = false` — plaintext creds OK inside the
  vault.

Switch back to Pro strict defaults by dropping `--edition team` or setting
`KESTREL_EDITION=pro`.

---

## 🏗️ Architecture
>>>>>>> REPLACE
```

### Step 6 — verify_cmd

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/team/test_bootstrap.py -v
```

### Step 7 — full_verify

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

### Step 8 — CLI smoke (manual, for post-check)

执行者跑这条，**该 RFC 不把它包成 RUN step**（不在 whitelist 前缀内可能有差
异；只作为人工校验）：

```powershell
.venv\Scripts\python.exe -m kestrel_mcp --edition team team bootstrap --dry-run --name smoke-test --scope "test.local"
```

应看到 Bootstrap Report banner 含 `smoke-test` 和 `test.local`。

## Tests

Step 4 含 6 个测试：
- dry-run 不写盘
- 渲染函数含关键字符串
- doctor warnings 进渲染
- 真 bootstrap 建 engagement + sqlite
- 空 scope 也能建
- 显式 edition='pro' 被尊重

## Post-checks

- [ ] `git diff --stat` 只列 `files_will_touch`
- [ ] `pytest tests/unit/team/test_bootstrap.py` 6 passed
- [ ] `full_verify.py` 仍 8/8
- [ ] 人工：`kestrel --edition team team bootstrap --dry-run --name smoke`
      输出 banner + scope + Next steps
- [ ] 第二次执行同一 name：应该报 `Engagement name '<name>' already exists`
      (UniqueConstraintError) — 不是崩，是明确 error
- [ ] `Remove-Item $env:USERPROFILE\.kestrel\data.db` 可以清理测试残留

## Rollback plan

见 front-matter `rollback_cmd`。注意：如果执行过真 bootstrap，`~/.kestrel/data.db`
里有测试 engagement — 手动删除，否则下次 smoke 同名会冲突。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加 `RFC-T08 closes Team edition bootstrap
  command`
- `rfcs/INDEX.md` → RFC-T08 状态 `done`，Team MVP 三件套全绿
- `README.md` → Step 5 已加 Team Edition Quickstart 章节

## Notes for executor

- **ServiceContainer.default_on_disk** 签名是 `(*, data_dir: Path | None = None)`
  — **全 keyword-only**。不要写成 `default_on_disk(path)`。
- **EngagementService.create** 全 keyword-only，必填：`name`, `display_name`,
  `engagement_type`, `client`。v1 漏了 3 个，v2 按真实签名补齐。
- **engagement_type**：用 `ent.EngagementType.RED_TEAM`（不是 `CTF`，因为
  PRODUCT_LINES 决策 5 明确砍 CTF domain 概念）。
- **name 是 slug**：字符仅限 `[a-z0-9_-]`（见 entities.py `_SLUG_CHARS`）。如果
  用户传含大写或特殊字符的 name，domain 层会在 create 时验证失败。本 RFC 不做
  前置规范化（让 domain 报错，UX 再加时改）。
- **Typer `Annotated`**：`__main__.py` 顶部已有 `from typing import Annotated`
  （RFC-A04 执行时已加）；不要重复 import。
- **`typer.Option("--name", "-n")`**：`-n` 作为短选项。v1 也这样，此处保留。
- **asyncio.run in bootstrap()**：Typer handler 是 sync 函数；用 `asyncio.run`
  起 async core。测试里 `bootstrap()` 直接同步调用，pytest 的 asyncio 不会冲突。
- **测试 tmp 目录**：用 `monkeypatch.setenv("KESTREL_DATA_DIR", str(tmp_path))`
  隔离每个测试。`Path.home()` 在 Windows/Linux 行为不同，但我们通过 env 强制
  固定位置。
- **team/__init__.py 必须存在且可空**：pytest rootdir 检测 Python 包靠它；若
  省略，`tests/unit/team/test_bootstrap.py` 的 import 可能失败。

## Changelog

- **2026-04-21 v1.0** — Initial spec. FAILED pre-flight (3 SEARCH
  hallucinations, 1 WRITE-not-in-fwt, wrong EngagementService.create
  signature, wrong ServiceContainer.default_on_disk signature).
- **2026-04-21 v2.0** — **Full rewrite** after reading real
  `core/services.py`, `domain/services/engagement_service.py`,
  `domain/entities.py::EngagementType`, `README.md`. All SEARCH blocks
  copied from real files. Added README Team Quickstart section. 6 tests.
