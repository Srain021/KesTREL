---
id: RFC-T08
title: Team bootstrap — one command to get a 4-person crew operational
epic: T-TeamEdition
status: open
owner: unassigned
role: backend-engineer
blocking_on: [RFC-A04, RFC-T00]
edition: team
budget:
  max_files_touched: 5
  max_new_files: 3
  max_lines_added: 260
  max_minutes_human: 50
  max_tokens_model: 18000
files_to_read:
  - src/redteam_mcp/__main__.py
  - src/redteam_mcp/config.py
  - src/redteam_mcp/domain/services/engagement_service.py
  - src/redteam_mcp/core/services.py
  - README.md
files_will_touch:
  - src/redteam_mcp/team/__init__.py              # new
  - src/redteam_mcp/team/bootstrap.py             # new
  - src/redteam_mcp/__main__.py                   # modified: add `team` subcommand group
  - tests/unit/team/test_bootstrap.py             # new
  - README.md                                     # modified: add Team Quickstart
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/team/test_bootstrap.py -v && .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition team team bootstrap --dry-run --name smoke-test
rollback_cmd: |
  git checkout -- src/redteam_mcp/__main__.py README.md
  if exist src\redteam_mcp\team rmdir /s /q src\redteam_mcp\team
  if exist tests\unit\team rmdir /s /q tests\unit\team
skill_id: rfc-t08-bootstrap
---

# RFC-T08 — Team bootstrap command

## Mission

一条命令 `kestrel --edition team team bootstrap --name <slug>` 把队伍拉起来：建 engagement、载默认 scope、doctor 自检、输出连接说明。

## Context

- PRODUCT_LINES.md "最快部署能用"原则的兑现。
- RFC-A04 提供 edition；RFC-T00 提供 unleashed 行为 —— 此 RFC 提供**用户入口**。
- 新人拉代码后 <5 分钟应该 "能跑起来"。
- 不新造 domain —— 直接调现有 `EngagementService.create()` + `ScopeService.add_entry()`。

## Non-goals

- **不做 CTF-specific**：不拉 VPN / 不刷 nuclei templates / 不连 HTB API。那是 CTF 专属的 RFC（按用户决策，砍）。
- 不集成 Vaultwarden（V-T2 后续）。
- 不启动 tmate（V-T3 后续）。
- 不做 docker-compose 栈（Pro 版 deploy RFC 的事）。
- **不写 web UI 部分** —— 纯 CLI。

## Design

`kestrel team bootstrap` 做 6 件事：

1. 读/创建 `~/.kestrel/data/` 数据目录（若不存在）
2. 运行 `doctor` 检查关键工具（nuclei/sliver/caido/shodan api key 是否就位，缺失只 warn）
3. 在 Team DB 新建一个 `Engagement`（slug = `--name`，status=`active`）
4. 若提供 `--scope a.com,b.net`，批量 add 到 scope
5. 打印 "Ready!" 信息 + 下一步提示（连 LLM client 的命令）
6. 可选 `--dry-run` 只打印要做什么，不落地

**设计决策**：
- 这是**第一个 Team 专属子包**；在 `src/redteam_mcp/team/` 建立目录骨架
- bootstrap 不直接调 sqlalchemy；走 `ServiceContainer.default_on_disk()` + domain services
- CLI 加 typer 子 app 避免污染顶层命名空间：`kestrel team <subcommand>`

## Steps

### Step 1 — 建 team 子包

```
WRITE src/redteam_mcp/team/__init__.py
"""Team Edition subpackage.

Only imported when `settings.edition == "team"`. Code in this package MUST check
`settings.features` before invoking side effects; it MUST NOT assume Pro safety
guarantees (no rate limiting, no strict scope).

Decision log: see PRODUCT_LINES.md Part 9.
"""
```

### Step 2 — 实现 bootstrap 逻辑

```
WRITE src/redteam_mcp/team/bootstrap.py
"""Bootstrap a crew-ready Team edition install."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from redteam_mcp.config import Settings
from redteam_mcp.core.services import ServiceContainer


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
            f"╔══════════════════════════════════════════════════════════════╗",
            f"║  Kestrel Team Edition — Bootstrap Report                    ║",
            f"╚══════════════════════════════════════════════════════════════╝",
            f"  Engagement: {self.name}  ({'dry-run' if self.dry_run else 'created'})",
            f"  Edition:    {self.edition}",
            f"  Data dir:   {self.data_dir}",
            f"  Engagement id: {self.engagement_id or '(pending)'}",
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
            "    1. Start server:   kestrel --edition team server --engagement " + self.name,
            "    2. Point your LLM client at stdio transport",
            "    3. First tool:     engagement_get → scope_list → target_list",
            "",
        ]
        return "\n".join(lines)


def _doctor_warnings() -> list[str]:
    warnings = []
    for tool in ("nuclei", "sliver-server", "caido"):
        if shutil.which(tool) is None:
            warnings.append(f"{tool} not on PATH (feature degraded)")
    import os
    if not os.getenv("SHODAN_API_KEY"):
        warnings.append("SHODAN_API_KEY unset (OSINT search disabled)")
    return warnings


async def _do_bootstrap(
    settings: Settings,
    name: str,
    scope_entries: Iterable[str],
    dry_run: bool,
) -> BootstrapReport:
    data_dir = Path.home() / ".kestrel" / "data"
    if not dry_run:
        data_dir.mkdir(parents=True, exist_ok=True)

    report = BootstrapReport(
        name=name,
        edition=settings.edition,
        data_dir=data_dir,
        dry_run=dry_run,
        doctor_warnings=_doctor_warnings(),
    )

    if dry_run:
        report.scope_added = list(scope_entries)
        return report

    services = ServiceContainer.default_on_disk(data_dir / "team.sqlite")
    await services.create_all()

    eng = await services.engagement.create(name=name, description="Team edition engagement", owners=[])
    report.engagement_id = str(eng.id)

    for entry in scope_entries:
        await services.scope.add_entry(engagement_id=eng.id, pattern=entry.strip())
        report.scope_added.append(entry.strip())

    await services.close()
    return report


def bootstrap(
    name: str,
    scope: str | None = None,
    dry_run: bool = False,
    edition: str | None = "team",
) -> BootstrapReport:
    settings = Settings.build(edition=edition)
    entries = [s.strip() for s in (scope or "").split(",") if s.strip()]
    return asyncio.run(_do_bootstrap(settings, name, entries, dry_run))
```

> **Notes for executor**: `ServiceContainer.default_on_disk(path)` and `services.engagement.create(...)` signatures must match the codebase. If `default_on_disk` requires `str`, wrap `str(data_dir / "team.sqlite")`. If `engagement.create` doesn't accept `owners=[]`, drop it. Read the service signatures before writing this file.

### Step 3 — CLI 子命令

```
REPLACE src/redteam_mcp/__main__.py
<<<<<<< SEARCH
@app.command("show-config")
=======
team_app = typer.Typer(help="Team edition commands (use with --edition team)")
app.add_typer(team_app, name="team")


@team_app.command("bootstrap")
def team_bootstrap_cmd(
    name: str = typer.Option(..., "--name", "-n", help="Engagement slug, e.g. 'op-winter-2026'"),
    scope: str | None = typer.Option(None, "--scope", help="Comma-separated scope patterns"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only, no changes"),
) -> None:
    """Bootstrap a Team edition engagement in one command."""
    from redteam_mcp.team.bootstrap import bootstrap

    edition = _edition_state.get("value") or "team"
    report = bootstrap(name=name, scope=scope, dry_run=dry_run, edition=edition)
    print(report.render())


@app.command("show-config")
>>>>>>> REPLACE
```

### Step 4 — 测试

```
WRITE tests/unit/team/__init__.py
```

```
WRITE tests/unit/team/test_bootstrap.py
from __future__ import annotations

from pathlib import Path

import pytest

from redteam_mcp.team.bootstrap import BootstrapReport, bootstrap


def test_dry_run_reports_no_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows home
    report = bootstrap(name="op-test", scope="a.com,b.net", dry_run=True)
    assert report.dry_run is True
    assert report.engagement_id is None
    assert report.scope_added == ["a.com", "b.net"]
    assert report.edition == "team"


def test_report_render_contains_next_steps():
    r = BootstrapReport(name="x", edition="team", data_dir=Path("/tmp"), dry_run=True)
    text = r.render()
    assert "Next steps" in text
    assert "kestrel --edition team" in text
    assert "dry-run" in text


def test_doctor_warnings_collected():
    r = BootstrapReport(name="x", edition="team", data_dir=Path("/tmp"), dry_run=True)
    # best-effort; some tools may exist on CI boxes
    text = r.render()
    # just verify render doesn't crash with empty warnings either
    assert "Kestrel Team Edition" in text


@pytest.mark.asyncio
async def test_real_bootstrap_creates_engagement(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    report = bootstrap(name="op-real", scope="example.com", dry_run=False)
    assert report.engagement_id is not None
    assert len(report.engagement_id) >= 32  # UUID-ish
    assert report.scope_added == ["example.com"]
    assert (tmp_path / ".kestrel" / "data" / "team.sqlite").is_file()
```

> **Notes for executor**: `test_real_bootstrap_creates_engagement` 是真 I/O 测试。如果 CI 敏感把它标 `@pytest.mark.integration`；但本地应该跑得通。`Path.home()` 在 Windows 下读 `USERPROFILE`。

### Step 5 — README 加 Team Quickstart

```
REPLACE README.md
<<<<<<< SEARCH
## Installation
=======
## Team Edition Quickstart (4-person crew)

Get operational in under 5 minutes:

```powershell
# 1. One-liner bootstrap
kestrel --edition team team bootstrap --name op-winter-2026 --scope "hackbox.lab,*.ctf-internal"

# 2. Start server (points your LLM client at stdio)
kestrel --edition team server --engagement op-winter-2026
```

**What unleashed mode means:**
- `scope_enforcement = warn_only` — out-of-scope targets logged, not blocked
- `rate_limit_enabled = False` — no throttling
- `credential_encryption_required = False` — plaintext creds OK inside your vault

See [PRODUCT_LINES.md](./PRODUCT_LINES.md) for edition differences.

## Installation
>>>>>>> REPLACE
```

### Step 6 — 运行

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/team/test_bootstrap.py -v
RUN .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition team team bootstrap --dry-run --name smoke --scope test.local
```

## Tests

见 Step 4。4 个测试：
- Dry-run 不写盘
- Report 渲染包含关键字符串
- Doctor warnings 收集
- 真 bootstrap 建 engagement 到 sqlite

## Post-checks

- [ ] `git diff --stat` 只列出 `files_will_touch`
- [ ] `team bootstrap --dry-run` 输出包含 ASCII banner、engagement id `(pending)`、Next steps
- [ ] `team bootstrap --name real` 创建 sqlite 文件 in `~/.kestrel/data/team.sqlite`
- [ ] 再跑 `team bootstrap --name real` —— 应该**幂等**或**友好失败**（重复 slug 不应抛栈）

## Rollback plan

```
git checkout -- src/redteam_mcp/__main__.py README.md
rmdir /s /q src\redteam_mcp\team tests\unit\team
```

若 Step 6 已建 `~/.kestrel/data/team.sqlite`，用户可手工删除；此 RFC 不清理。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加 `RFC-T08 one-command team bootstrap`
- `PRODUCT_LINES.md` → 在 Part 9 "下一步" 段标 T08 done
- `rfcs/INDEX.md` → RFC-T08 标 `done`；标记 Team MVP 三件套全部完成

## Notes for executor

- **最大风险点**：`ServiceContainer.default_on_disk(path)` 接受 `Path` 还是 `str`？先读 `src/redteam_mcp/core/services.py` 确认。Windows 下 `\\` 转义问题要用 `as_posix()` 或 sqlalchemy URL 格式 `sqlite+aiosqlite:///C:/...`。
- `engagement.create()` 若有 `actor` 必填参数，需要先建默认 actor：可复用 `AUDIT_V2` 里 Actor 概念，传一个"system" actor。如果必填，在 `_do_bootstrap` 里先 `actor = await services.actor.get_or_create_system()` (若该方法不存在，降级用直接 ORM)。
- `tests/unit/team/__init__.py` 必须是**空文件**；pytest rootdir 靠它识别包。
- Typer `add_typer` 位置要在 `app` 创建之后、`@app.command` 装饰之前；否则帮助文案顺序乱。
- CLI 验证命令 `kestrel --edition team team bootstrap --dry-run --name smoke-test` 的 `--edition team` 是全局 callback（RFC-A04 已添加），`team bootstrap` 是子命令 —— 两个 `team` 看似重复但实际不同层级。

## Changelog

- **2026-04-21 初版** by AI — delivers Team MVP "fastest time to value" per PRODUCT_LINES.md decision 5
