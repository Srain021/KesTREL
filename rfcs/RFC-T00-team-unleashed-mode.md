---
id: RFC-T00
title: Team unleashed mode — disable scope, rate limit, encryption when edition=team
epic: T-TeamEdition
status: open
owner: unassigned
role: backend-engineer
blocking_on: [RFC-A04]
edition: team
budget:
  max_files_touched: 6
  max_new_files: 1
  max_lines_added: 180
  max_minutes_human: 40
  max_tokens_model: 16000
files_to_read:
  - src/redteam_mcp/server.py
  - src/redteam_mcp/security.py
  - src/redteam_mcp/core/rate_limit.py
  - src/redteam_mcp/domain/services/scope_service.py
  - src/redteam_mcp/features.py
files_will_touch:
  - src/redteam_mcp/server.py                # modified: gate scope + rate limit
  - src/redteam_mcp/security.py              # modified: honor warn_only
  - src/redteam_mcp/core/rate_limit.py       # modified: no-op when disabled
  - src/redteam_mcp/core/context.py          # modified: enforce features
  - tests/unit/test_team_unleashed.py        # new
  - CHANGELOG.md                             # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_team_unleashed.py tests/unit/test_editions.py -v && .venv\Scripts\python.exe scripts\full_verify.py
rollback_cmd: |
  git checkout -- src/redteam_mcp/server.py src/redteam_mcp/security.py src/redteam_mcp/core/rate_limit.py src/redteam_mcp/core/context.py CHANGELOG.md
  if exist tests\unit\test_team_unleashed.py del tests\unit\test_team_unleashed.py
skill_id: rfc-t00-unleashed
---

# RFC-T00 — Team unleashed mode

## Mission

Team edition 启动时，scope 检查降为 warn-only、rate limit 完全跳过、credential encryption 变可选。

## Context

- PRODUCT_LINES.md 决策 4 + 5：用户明确"就是要无限制，最快能用"。
- RFC-A04 已提供 `FeatureFlags` 基建；此 RFC **只消费**，不新增 flags。
- Pro 行为零影响（`edition=pro` 保持 Pydantic 默认 = 严格模式）。
- 无新 domain 实体（**不做** V-D1..D5）—— 纯 feature gate。

## Non-goals

- 不做 `--unleash` 的一次性命令（因为 Team edition 本身就是 unleashed，没必要第二个开关）。
- 不做 Pro 版的 `disable` 反向开关（Pro 永远 strict，除非用户手工改 config yaml）。
- 不做审计日志增强（warn_only 的 scope miss 已经走 `logger.warning`）。
- 不改 CLI；复用 RFC-A04 的 `--edition team`。

## Design

三个执行点，每个加 `if not features.X: return` 短路：

1. **`security.ScopeGuard.check_target()`** 和 **`ScopeService.ensure()`** —— 在 block 前读 `features.scope_enforcement`：
   - `strict` → 当前行为（抛 `AuthorizationError`）
   - `warn_only` → `logger.warning` + 允许通过
   - `off` → 静默通过
2. **`RateLimiter.acquire()`** —— 第一行加 `if not features.rate_limit_enabled: return True`
3. **`CredentialService.store()`**（若存在；若 RFC-003 未完成则在 code 中加 TODO）—— 读 `features.credential_encryption_required`，False 时允许明文

`features` 怎么拿到：从 `RequestContext.current_context_or_none().settings.features`。`RequestContext` 需要持有 Settings 引用。

## Steps

### Step 1 — RequestContext 暴露 features

```
REPLACE src/redteam_mcp/core/context.py
<<<<<<< SEARCH
@dataclass(frozen=True, slots=True)
class RequestContext:
=======
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redteam_mcp.features import FeatureFlags


@dataclass(frozen=True, slots=True)
class RequestContext:
>>>>>>> REPLACE
```

在 RequestContext 加 `features` 字段（位置在 `engagement_id` 附近，executor 定位）：

```
REPLACE src/redteam_mcp/core/context.py
<<<<<<< SEARCH
    dry_run: bool = False
=======
    dry_run: bool = False
    features: "FeatureFlags | None" = None  # None = use Pro defaults
>>>>>>> REPLACE
```

加 helper:

```
REPLACE src/redteam_mcp/core/context.py
<<<<<<< SEARCH
def current_context_or_none() -> RequestContext | None:
=======
def current_features():
    """Return FeatureFlags from current context, or Pro defaults."""
    ctx = current_context_or_none()
    if ctx is not None and ctx.features is not None:
        return ctx.features
    from redteam_mcp.features import FeatureFlags
    return FeatureFlags()


def current_context_or_none() -> RequestContext | None:
>>>>>>> REPLACE
```

### Step 2 — server 把 features 注入 RequestContext

```
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
        ctx = RequestContext(
=======
        features = getattr(self._settings, "features", None)
        ctx = RequestContext(
>>>>>>> REPLACE
```

在紧跟的 `RequestContext(...)` 构造里加 `features=features,` —— executor 找到并在括号结束前插入。

> **Notes for executor**: `self._settings` 可能叫 `settings` 或 `self.settings`，按实际代码名。

### Step 3 — ScopeGuard honor warn_only

```
REPLACE src/redteam_mcp/security.py
<<<<<<< SEARCH
def check_target(self, target: str) -> None:
=======
def check_target(self, target: str) -> None:
    from redteam_mcp.core.context import current_features

    enforcement = current_features().scope_enforcement
    if enforcement == "off":
        return
    try:
        self._strict_check(target)
    except Exception:
        if enforcement == "warn_only":
            import structlog
            structlog.get_logger(__name__).warning(
                "scope.warn_only", target=target, note="out of scope but allowed (team edition)"
            )
            return
        raise

def _strict_check(self, target: str) -> None:
>>>>>>> REPLACE
```

> **Notes for executor**: 原有 `check_target` 方法体被**整体搬进** `_strict_check`。要先把旧方法体 cut 出来 paste 到 `_strict_check` 下；`_strict_check` 签名保持 `(self, target: str) -> None`。如果 `security.py` 用不同命名（比如 `authorize`），相应改。

### Step 4 — ScopeService.ensure() 同样处理

```
REPLACE src/redteam_mcp/domain/services/scope_service.py
<<<<<<< SEARCH
    async def ensure(self, engagement_id, target: str) -> None:
=======
    async def ensure(self, engagement_id, target: str) -> None:
        from redteam_mcp.core.context import current_features

        enforcement = current_features().scope_enforcement
        if enforcement == "off":
            return
        try:
            await self._strict_ensure(engagement_id, target)
        except Exception:
            if enforcement == "warn_only":
                self._log.warning(
                    "scope.warn_only", target=target, engagement_id=str(engagement_id)
                )
                return
            raise

    async def _strict_ensure(self, engagement_id, target: str) -> None:
>>>>>>> REPLACE
```

旧 `ensure` 方法体搬进 `_strict_ensure`（同 Step 3 做法）。

### Step 5 — RateLimiter 短路

```
REPLACE src/redteam_mcp/core/rate_limit.py
<<<<<<< SEARCH
    async def acquire(self, key: str) -> bool:
=======
    async def acquire(self, key: str) -> bool:
        from redteam_mcp.core.context import current_features

        if not current_features().rate_limit_enabled:
            return True
>>>>>>> REPLACE
```

### Step 6 — 测试

```
WRITE tests/unit/test_team_unleashed.py
from __future__ import annotations

import pytest

from redteam_mcp.core.context import RequestContext, bind_context, current_features
from redteam_mcp.editions import TEAM_DEFAULTS, PRO_DEFAULTS
from redteam_mcp.features import FeatureFlags


def test_current_features_returns_pro_default_when_no_context():
    assert current_features().scope_enforcement == "strict"


def test_current_features_reads_team_from_context():
    ctx = RequestContext(
        services=None, engagement_id=None, actor=None, dry_run=False, features=TEAM_DEFAULTS
    )
    with bind_context(ctx):
        assert current_features().scope_enforcement == "warn_only"
        assert current_features().rate_limit_enabled is False


@pytest.mark.asyncio
async def test_ratelimiter_disabled_short_circuits():
    from redteam_mcp.core.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("foo", rate=1, capacity=1)

    # pro: enforces
    ctx_pro = RequestContext(
        services=None, engagement_id=None, actor=None, dry_run=False, features=PRO_DEFAULTS
    )
    with bind_context(ctx_pro):
        ok1 = await rl.acquire("foo")
        ok2 = await rl.acquire("foo")
        assert ok1 is True
        assert ok2 is False  # bucket exhausted

    # team: always allows
    ctx_team = RequestContext(
        services=None, engagement_id=None, actor=None, dry_run=False, features=TEAM_DEFAULTS
    )
    with bind_context(ctx_team):
        for _ in range(10):
            assert await rl.acquire("foo") is True


def test_scope_guard_warn_only(caplog):
    from redteam_mcp.security import ScopeGuard

    guard = ScopeGuard(scope=["*.example.com"])
    ctx_team = RequestContext(
        services=None, engagement_id=None, actor=None, dry_run=False, features=TEAM_DEFAULTS
    )
    with bind_context(ctx_team):
        guard.check_target("evil.attacker.io")  # would raise in strict


def test_scope_guard_strict_still_blocks():
    from redteam_mcp.security import ScopeGuard
    from redteam_mcp.core_errors import AuthorizationError  # or equivalent

    guard = ScopeGuard(scope=["*.example.com"])
    ctx_pro = RequestContext(
        services=None, engagement_id=None, actor=None, dry_run=False, features=PRO_DEFAULTS
    )
    with bind_context(ctx_pro):
        with pytest.raises(Exception):
            guard.check_target("evil.attacker.io")
```

> **Notes for executor**:
> - `bind_context` 和 `current_features` 是 Step 1 添加的。
> - `AuthorizationError` 的准确路径按 `core_errors.py` 确认。如果测试依赖的类名不对，用通用 `pytest.raises(Exception)`。
> - `ScopeGuard` 构造函数签名（`scope=` 或 `allowed=`）按 security.py 实际用法。
> - `RateLimiter.configure()` 若不存在，按现有接口调整（也许是 `__init__` 入参）。

### Step 7 — 运行验证

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/test_editions.py tests/unit/test_team_unleashed.py -v
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

- 4 个 `test_editions` 测试（RFC-A04 已有）全通过
- 5 个 `test_team_unleashed` 测试（本 RFC 新增）
- `full_verify.py` 的 8 项检查全通过（回归）

## Post-checks

- [ ] `git diff --stat` 只列出 `files_will_touch` 的 6 个文件
- [ ] `--edition team` 起服务后，访问一个 out-of-scope target → 日志里出现 `scope.warn_only`，但工具执行成功
- [ ] `--edition pro` 起服务后，同样操作 → 抛 `AuthorizationError`
- [ ] RateLimiter 在 team edition 下连续调用不会节流

## Rollback plan

```
git checkout -- src/redteam_mcp/server.py src/redteam_mcp/security.py src/redteam_mcp/core/rate_limit.py src/redteam_mcp/core/context.py CHANGELOG.md
del tests\unit\test_team_unleashed.py
```

RFC-A04 不受影响（仍可独立存在）。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加 `RFC-T00 enables Team edition unleashed mode`
- `AUDIT_V2.md` → 标 V-A1/V-A2 为"Team 侧完成"
- `rfcs/INDEX.md` → RFC-T00 标 `done`；Epic T 更新
- `LLM_GUIDANCE.md` → 加一段「Team edition 下 scope 不 block，仍要克制」

## Notes for executor

- `ScopeGuard.check_target()` / `ScopeService.ensure()` 的"把旧方法体挪到 `_strict_xxx`"操作是**最容易出错**的。**先读整个方法再动手**。
- 如果发现 `ScopeGuard` 已经有 `_strict_check` 命名冲突（不太可能），改成 `_check_target_strict`。
- `logger.warning` 的格式遵循现有 structlog 用法；如果代码用 `logging` 而非 `structlog`，按现状沿用。
- `current_features()` 是 Step 1 添加的新 helper —— **不要**提前导入它的现有代码（可能触发循环）。全部用**函数内 lazy import**：`from redteam_mcp.core.context import current_features`。
- 测试里 `features=TEAM_DEFAULTS` 传入 `RequestContext`，Pydantic 的 `dataclass(frozen=True, slots=True)` 可能不接 TypedDict —— 传 `FeatureFlags` 实例才对。

## Changelog

- **2026-04-21 初版** by AI — implements "unleashed mode" per PRODUCT_LINES.md decision 4/5
