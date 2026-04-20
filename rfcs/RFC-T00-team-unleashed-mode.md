---
id: RFC-T00
title: Team unleashed mode — scope_enforcement three-state switch at server dispatch
epic: T-TeamEdition
status: done
owner: unassigned
role: backend-engineer
blocking_on: [RFC-A04]
edition: team
budget:
  max_files_touched: 4
  max_new_files: 1
  max_lines_added: 140
  max_minutes_human: 25
  max_tokens_model: 10000
files_to_read:
  - src/redteam_mcp/server.py
  - src/redteam_mcp/security.py
  - src/redteam_mcp/features.py
files_will_touch:
  - src/redteam_mcp/server.py                # modified: _check_scope feature-aware
  - tests/unit/test_team_unleashed.py        # new
  - CHANGELOG.md                             # modified
  - rfcs/INDEX.md                            # modified (status done + unblock T08)
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_team_unleashed.py -v
rollback_cmd: |
  git checkout -- src/redteam_mcp/server.py CHANGELOG.md rfcs/INDEX.md
  if exist tests\unit\test_team_unleashed.py del tests\unit\test_team_unleashed.py
skill_id: rfc-t00-unleashed
---

# RFC-T00 — Team unleashed mode

## Mission

Team edition 启动时，scope 违规从 raise 降级为 warn-only（或可完全关）—— 只改
`server._check_scope` 一个方法。

## Context

- PRODUCT_LINES.md 决策 4：Team edition 要"就是要无限制"。
- RFC-A04 已提供 `Settings.features.scope_enforcement: "strict"|"warn_only"|"off"`。
  本 RFC 只消费它。
- v1 RFC 失败于 6 个 SEARCH 幻觉（见 RFC_AUDIT_PREFLIGHT.md），因为作者写 spec
  时没读真实 `server.py` / `security.py` / `scope_service.py`。v2 范围彻底简化：
  **不再改 security/scope_service/context/rate_limit** — 所有逻辑放在 `server
  ._check_scope` 这个已有的单一 authorization 入口。
- **Rate limit bypass 已从本 RFC 移出**。那需要 `core/rate_limit.py` 存在
  （RFC-004），本 RFC 不做。留给未来 RFC-T00b。

## Non-goals

- 不改 `ScopeGuard.ensure()` 签名（会影响测试 / legacy 调用点）。
- 不改 `ScopeService.ensure()` 签名。
- 不改 `RequestContext` 结构。
- 不做 rate_limit / credential encryption 的 feature gate（留给后续 RFC）。
- 不加新命令行 flag。`--edition team` 已是 A04 的职责。

## Design

单一改动点：`RedTeamMCPServer._check_scope()`（`server.py` 约 247-265 行）。

```
strict    (Pro default)  → 当前行为（raise AuthorizationError / ScopeViolationError）
warn_only (Team default) → try 原逻辑; 捕获异常后 log warning 并 return
off                      → 不做任何检查，直接 return
```

实现方式：在 method 开头读 `self.settings.features.scope_enforcement`；strict/
warn_only 用 try/except 包裹原逻辑；off 直接 `return`。

**注意**：`self.settings.features` 是 Pydantic v2 frozen model（A04），读取零副
作用。

## Steps

### Step 1 — 替换 server._check_scope

```
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
    async def _check_scope(
        self,
        ctx: RequestContext,
        target: str,
        tool_name: str,
    ) -> None:
        """Central scope check.

        Precedence:
            1. If the context has an active engagement, the persistent
               :class:`ScopeService` is authoritative.
            2. Otherwise fall back to the in-memory :class:`ScopeGuard`
               (legacy mode / pre-engagement workflows).
        """

        if ctx.has_engagement():
            await ctx.ensure_scope(target, tool_name=tool_name)
            return
        self.scope_guard.ensure(target, tool_name=tool_name)
=======
    async def _check_scope(
        self,
        ctx: RequestContext,
        target: str,
        tool_name: str,
    ) -> None:
        """Central scope check, honoring ``FeatureFlags.scope_enforcement``.

        Precedence:
            1. If the context has an active engagement, the persistent
               :class:`ScopeService` is authoritative.
            2. Otherwise fall back to the in-memory :class:`ScopeGuard`
               (legacy mode / pre-engagement workflows).

        Feature-flag behavior (RFC-T00):

        * ``strict``    (Pro default): violations raise.
        * ``warn_only`` (Team default): violations logged and allowed.
        * ``off``       : no check at all.
        """

        enforcement = self.settings.features.scope_enforcement
        if enforcement == "off":
            return
        try:
            if ctx.has_engagement():
                await ctx.ensure_scope(target, tool_name=tool_name)
                return
            self.scope_guard.ensure(target, tool_name=tool_name)
        except (AuthorizationError, ScopeViolationError) as exc:
            if enforcement == "warn_only":
                self.log.warning(
                    "scope.warn_only",
                    tool=tool_name,
                    target=target,
                    reason=str(exc),
                    engagement_id=str(ctx.engagement_id) if ctx.engagement_id else None,
                )
                return
            raise
>>>>>>> REPLACE
```

### Step 2 — 测试

```
WRITE tests/unit/test_team_unleashed.py
```
```python
"""Tests for RFC-T00: scope_enforcement three-state switch in server._check_scope."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from redteam_mcp.domain.errors import ScopeViolationError
from redteam_mcp.features import FeatureFlags
from redteam_mcp.security import AuthorizationError, ScopeGuard
from redteam_mcp.server import RedTeamMCPServer


def _fake_server(scope_enforcement: str, authorized_scope: list[str] | None = None):
    """Build a minimal object with the attributes _check_scope reads."""
    fake = MagicMock(spec=RedTeamMCPServer)
    fake.settings = MagicMock()
    fake.settings.features = FeatureFlags(scope_enforcement=scope_enforcement)
    fake.scope_guard = ScopeGuard(authorized_scope or [])
    fake.log = MagicMock()
    return fake


def _fake_ctx_no_engagement():
    ctx = MagicMock()
    ctx.has_engagement.return_value = False
    ctx.engagement_id = None
    return ctx


@pytest.mark.asyncio
async def test_strict_raises_on_empty_scope():
    fake = _fake_server("strict", authorized_scope=[])
    ctx = _fake_ctx_no_engagement()
    with pytest.raises(AuthorizationError):
        await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")


@pytest.mark.asyncio
async def test_strict_raises_on_out_of_scope():
    fake = _fake_server("strict", authorized_scope=["example.com"])
    ctx = _fake_ctx_no_engagement()
    with pytest.raises(AuthorizationError):
        await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")


@pytest.mark.asyncio
async def test_strict_passes_on_in_scope():
    fake = _fake_server("strict", authorized_scope=["example.com"])
    ctx = _fake_ctx_no_engagement()
    # No exception expected.
    await RedTeamMCPServer._check_scope(fake, ctx, "example.com", "tool_x")


@pytest.mark.asyncio
async def test_warn_only_logs_out_of_scope_but_allows():
    fake = _fake_server("warn_only", authorized_scope=["example.com"])
    ctx = _fake_ctx_no_engagement()
    # Should NOT raise.
    await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")
    # Should have emitted a warning.
    fake.log.warning.assert_called_once()
    args, kwargs = fake.log.warning.call_args
    assert args[0] == "scope.warn_only"
    assert kwargs.get("target") == "attacker.io"
    assert kwargs.get("tool") == "tool_x"


@pytest.mark.asyncio
async def test_warn_only_still_logs_on_empty_scope():
    # Empty scope normally raises "authorized_scope is empty".
    fake = _fake_server("warn_only", authorized_scope=[])
    ctx = _fake_ctx_no_engagement()
    await RedTeamMCPServer._check_scope(fake, ctx, "anywhere.io", "tool_x")
    fake.log.warning.assert_called_once()


@pytest.mark.asyncio
async def test_off_skips_check_entirely():
    # Even an empty scope is silently accepted.
    fake = _fake_server("off", authorized_scope=[])
    ctx = _fake_ctx_no_engagement()
    await RedTeamMCPServer._check_scope(fake, ctx, "wherever.io", "tool_x")
    # No log call expected — check was short-circuited.
    fake.log.warning.assert_not_called()


@pytest.mark.asyncio
async def test_warn_only_handles_scope_service_violation():
    # When ctx has an engagement, ensure_scope is used; simulate it raising.
    fake = _fake_server("warn_only", authorized_scope=["example.com"])
    ctx = MagicMock()
    ctx.has_engagement.return_value = True
    ctx.engagement_id = "00000000-0000-0000-0000-000000000001"

    async def _raise(*a, **kw):
        raise ScopeViolationError(
            "out of scope",
            engagement_id=ctx.engagement_id,
            tool="tool_x",
            target="attacker.io",
        )

    ctx.ensure_scope = _raise
    # Should NOT raise.
    await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")
    fake.log.warning.assert_called_once()


@pytest.mark.asyncio
async def test_strict_propagates_scope_service_violation():
    fake = _fake_server("strict", authorized_scope=["example.com"])
    ctx = MagicMock()
    ctx.has_engagement.return_value = True
    ctx.engagement_id = "00000000-0000-0000-0000-000000000001"

    async def _raise(*a, **kw):
        raise ScopeViolationError(
            "out of scope",
            engagement_id=ctx.engagement_id,
            tool="tool_x",
            target="attacker.io",
        )

    ctx.ensure_scope = _raise
    with pytest.raises(ScopeViolationError):
        await RedTeamMCPServer._check_scope(fake, ctx, "attacker.io", "tool_x")
```

### Step 3 — verify_cmd

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/test_team_unleashed.py -v
```

### Step 4 — full_verify

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

Step 2 含 8 个测试：
- strict 三路径：empty / out-of-scope / in-scope
- warn_only 三路径：out-of-scope / empty scope / 通过 ScopeService
- off：完全跳过检查
- strict 经 ScopeService 的异常传播

所有测试用 `MagicMock(spec=RedTeamMCPServer)` 构造最小 fake server，不启动 MCP
协议或加载 tool modules — 单元测试级别，无外部依赖。

## Post-checks

- [ ] `git diff --stat` 只列 `files_will_touch` 的 4 项
- [ ] `pytest tests/unit/test_team_unleashed.py` 8 passed
- [ ] `full_verify.py` 仍 8/8（原 105 tests + 8 新 = 113 tests 或相近）
- [ ] `kestrel --edition pro show-config` 仍显示 `scope_enforcement: "strict"`
- [ ] `kestrel --edition team show-config` 仍显示 `scope_enforcement: "warn_only"`
- [ ] 人工烟囱测试（**可选**）：起 server 两次（pro / team edition），对一个
      out-of-scope target 调 nuclei_scan，pro 拒绝、team 仅 warning。

## Rollback plan

见 front-matter `rollback_cmd`。无数据库副作用，零迁移。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加 `RFC-T00 closes Team edition unleashed
  scope enforcement`
- `rfcs/INDEX.md` → RFC-T00 状态改 `done`；RFC-T08 保持 `blocked ⚠` 直到自身
  重写完

## Notes for executor

- **唯一改动点**：`RedTeamMCPServer._check_scope`。不要碰 `security.py`，不要碰
  `scope_service.py`，不要碰 `core/context.py`。v1 的失败就是因为试图改 4 个
  地方。
- **SEARCH 块**：整段 `_check_scope` 方法都在 SEARCH 里。必须**按当前文件一字
  不差**拷贝（9 行，包含 docstring）。运行 `validate_rfc.py rfcs/RFC-T00-*.md`
  会验证此块唯一匹配。
- **测试 MagicMock**：`MagicMock(spec=RedTeamMCPServer)` 给 mock 加 spec 限定
  可以访问的属性 —— 未知属性会抛 `AttributeError`。这是刻意的，防止我们以为
  方法访问到了实际上没配的字段。
- **async test**: 本项目 pytest 配置了 `asyncio_mode = "auto"`（见
  pyproject.toml），所以 `@pytest.mark.asyncio` 可省；但本 RFC 的测试显式写上
  以增加可读性，两种方式都能跑。
- **ScopeViolationError 构造**：签名是
  `(msg, *, engagement_id, tool, target, [blocked_by])`；位置参数只有 msg。

## Changelog

- **2026-04-21 v1.0** — Initial spec (FAILED pre-flight: 6 SEARCH
  hallucinations, 1 files_will_touch gap, 1 missing dep; see
  RFC_AUDIT_PREFLIGHT.md §2).
- **2026-04-21 v2.0** — **Full rewrite** after reading real
  `server.py::_check_scope`. Scope collapsed to single method change. Rate
  limit / credential encryption gates moved to future RFC-T00b (depends on
  RFC-004). 8 tests, `MagicMock(spec=...)` strategy to avoid full server
  instantiation.
