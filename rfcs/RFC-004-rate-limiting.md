---
id: RFC-004
title: Per-tool rate limiting
epic: A-Foundations
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-002
budget:
  max_files_touched: 5
  max_new_files: 2
  max_lines_added: 220
  max_minutes_human: 20
  max_tokens_model: 10000
files_to_read:
  - src/redteam_mcp/tools/base.py
  - src/redteam_mcp/server.py
  - src/redteam_mcp/core/context.py
files_will_touch:
  - src/redteam_mcp/core/rate_limit.py          # new
  - src/redteam_mcp/tools/base.py                # modified (ToolSpec gets rate_limit field)
  - src/redteam_mcp/server.py                    # modified (dispatcher consults limiter)
  - tests/unit/core/test_rate_limit.py           # new
  - CHANGELOG.md                                 # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/core/test_rate_limit.py -v
rollback_cmd: |
  git checkout -- .
  if exist src\redteam_mcp\core\rate_limit.py del src\redteam_mcp\core\rate_limit.py
  if exist tests\unit\core\test_rate_limit.py del tests\unit\core\test_rate_limit.py
skill_id: rfc-004-rate-limit
---

# RFC-004 — Per-tool rate limiting

## Mission

为每个 ToolSpec 加可选 rate limit；超限时返回 `RateLimitedError`，自带 retry-after。

## Context

- THREAT_MODEL T-D1：LLM 无限循环调工具，烧 Shodan credits / 打挂 target。
- GAP_ANALYSIS G-S7 P1。
- 本 RFC 是轻量实现：进程内 token-bucket，按 (tool_name, engagement_id) 维度限流。
- 生产级别（跨进程 / 持久化）留给未来 RFC。

## Non-goals

- 不做跨进程限流（不引入 Redis）
- 不做复杂策略（等比退避、用户优先级）
- 不修改 MCP 协议（只在 server dispatcher 里拦截）
- 不改既有工具的默认行为 —— 不填 rate_limit 的工具仍无限制

## Design

### 算法

**Token bucket**：每个 (tool_name, engagement_id) key 维持一个 bucket：

- `capacity`: 桶里最多几个 token
- `refill_rate`: 每秒补多少 token
- 每次调用消费 1 token；< 1 则拒绝

简单 O(1)，无依赖，进程内。

### 集成点

- `ToolSpec` 加可选字段 `rate_limit: RateLimitSpec | None`，含 `per_minute` 和 `burst`
- 全局 `RateLimiter` 挂在 `ServiceContainer`（方便测试）
- Server dispatcher 在调用 handler 前调 `limiter.acquire(tool_name, engagement_id)`；拒绝则抛 `RateLimitedError`
- `RateLimitedError` 被 dispatcher 渲染成 `ToolResult.error("Rate limited, retry after Ns")`

### 默认策略建议（不强制）

后续 tool 作者在写 ToolSpec 时可填：

| Tool | per_minute | burst |
|------|-----------|-------|
| shodan_search | 10 | 3 |
| shodan_scan_submit | 2 | 1 |
| nuclei_scan | 5 | 2 |
| sliver_generate_implant | 3 | 1 |

本 RFC 不修改具体工具 —— 只提供机制。工具逐个填入可以走未来小 RFC。

## Steps

### Step 1 — 新建 rate_limit 模块

```
WRITE src/redteam_mcp/core/rate_limit.py
```
```python
"""In-process token-bucket rate limiter.

Used by the MCP server dispatcher to throttle per-(tool, engagement) call
rates, mitigating THREAT T-D1 (runaway tool calls).

Design constraints
------------------

* Zero external dependencies (no Redis, no files).
* Thread / asyncio safe via an ``asyncio.Lock`` per bucket.
* Monotonic clock to avoid NTP jumps.
* Buckets GC themselves after 10 minutes of inactivity so long-running
  servers don't leak memory with churny engagement ids.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Hashable

from ..core_errors import KestrelError


class RateLimitedError(KestrelError):
    error_code = "kestrel.rate_limited"
    user_actionable = True
    http_like_status = 429

    def __init__(self, key: Hashable, retry_after_sec: float) -> None:
        super().__init__(
            f"Rate limit exceeded for {key!r}. Retry after {retry_after_sec:.1f}s.",
            key=repr(key),
            retry_after_sec=retry_after_sec,
        )
        self.retry_after_sec = retry_after_sec


@dataclass
class RateLimitSpec:
    """Declared on a ToolSpec; controls the token bucket shape."""

    per_minute: float         # refill rate
    burst: int = 1            # bucket capacity


@dataclass
class _Bucket:
    capacity: int
    refill_rate_per_sec: float
    tokens: float = 0.0
    last_refill: float = 0.0
    last_access: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_GC_INACTIVITY_SEC = 600.0


class RateLimiter:
    """Process-wide token bucket registry."""

    def __init__(self) -> None:
        self._buckets: dict[Hashable, _Bucket] = {}
        self._registry_lock = asyncio.Lock()

    async def acquire(self, key: Hashable, spec: RateLimitSpec) -> None:
        """Consume one token. Raise RateLimitedError if none available."""

        async with self._registry_lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                now = time.monotonic()
                bucket = _Bucket(
                    capacity=spec.burst,
                    refill_rate_per_sec=spec.per_minute / 60.0,
                    tokens=float(spec.burst),
                    last_refill=now,
                    last_access=now,
                )
                self._buckets[key] = bucket
            bucket.last_access = time.monotonic()

        async with bucket.lock:
            self._refill(bucket)
            if bucket.tokens < 1.0:
                deficit = 1.0 - bucket.tokens
                retry_after = deficit / bucket.refill_rate_per_sec if bucket.refill_rate_per_sec > 0 else 60.0
                raise RateLimitedError(key, retry_after)
            bucket.tokens -= 1.0

    def _refill(self, bucket: _Bucket) -> None:
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        if elapsed <= 0:
            return
        bucket.tokens = min(
            bucket.capacity,
            bucket.tokens + elapsed * bucket.refill_rate_per_sec,
        )
        bucket.last_refill = now

    async def gc(self) -> int:
        """Remove buckets idle for > _GC_INACTIVITY_SEC. Returns count removed."""

        now = time.monotonic()
        async with self._registry_lock:
            to_drop = [
                k for k, b in self._buckets.items() if now - b.last_access > _GC_INACTIVITY_SEC
            ]
            for k in to_drop:
                self._buckets.pop(k, None)
        return len(to_drop)
```

### Step 2 — ToolSpec 加 rate_limit 字段

```
REPLACE src/redteam_mcp/tools/base.py
<<<<<<< SEARCH
    # ---- Extended guidance (optional but STRONGLY recommended) ----
    when_to_use: list[str] = field(default_factory=list)
=======
    # ---- Rate limiting (optional, see RFC-004) ----
    rate_limit: "RateLimitSpec | None" = None

    # ---- Extended guidance (optional but STRONGLY recommended) ----
    when_to_use: list[str] = field(default_factory=list)
>>>>>>> REPLACE
```

在 base.py 顶部加延迟 import：

```
REPLACE src/redteam_mcp/tools/base.py
<<<<<<< SEARCH
from ..config import Settings
from ..logging import get_logger
from ..security import ScopeGuard
=======
from ..config import Settings
from ..core.rate_limit import RateLimitSpec  # noqa: F401 — for ToolSpec.rate_limit type
from ..logging import get_logger
from ..security import ScopeGuard
>>>>>>> REPLACE
```

### Step 3 — Server dispatcher 接入

```
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
from .core import RequestContext, ServiceContainer
from .domain.errors import ScopeViolationError
=======
from .core import RequestContext, ServiceContainer
from .core.rate_limit import RateLimitedError, RateLimiter
from .domain.errors import ScopeViolationError
>>>>>>> REPLACE
```

```
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
        self.settings = settings
        self.log = get_logger("server")
=======
        self.settings = settings
        self.log = get_logger("server")
        self.limiter = RateLimiter()
>>>>>>> REPLACE
```

```
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
            async def _dispatch(ctx: RequestContext) -> ToolResult:
                if spec.requires_scope_field:
=======
            async def _dispatch(ctx: RequestContext) -> ToolResult:
                if spec.rate_limit is not None:
                    key = (name, str(ctx.engagement_id) if ctx.engagement_id else "<no-engagement>")
                    await self.limiter.acquire(key, spec.rate_limit)
                if spec.requires_scope_field:
>>>>>>> REPLACE
```

```
REPLACE src/redteam_mcp/server.py
<<<<<<< SEARCH
            except (AuthorizationError, ScopeViolationError) as exc:
                self.log.warning("tool.auth_denied", tool=name, reason=str(exc))
                return [TextContent(type="text", text=f"AUTHORIZATION DENIED: {exc}")]
=======
            except (AuthorizationError, ScopeViolationError) as exc:
                self.log.warning("tool.auth_denied", tool=name, reason=str(exc))
                return [TextContent(type="text", text=f"AUTHORIZATION DENIED: {exc}")]
            except RateLimitedError as exc:
                self.log.warning("tool.rate_limited", tool=name, retry_after=exc.retry_after_sec)
                return [TextContent(
                    type="text",
                    text=f"RATE LIMITED: {exc}. Pause {exc.retry_after_sec:.1f}s before retrying.",
                )]
>>>>>>> REPLACE
```

### Step 4 — 测试

```
WRITE tests/unit/core/test_rate_limit.py
```
```python
"""RateLimiter unit tests."""

from __future__ import annotations

import asyncio

import pytest

from redteam_mcp.core.rate_limit import (
    RateLimitedError,
    RateLimiter,
    RateLimitSpec,
)


async def test_initial_burst_allowed():
    lim = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=3)
    # burst = 3 → 3 consecutive acquires must succeed immediately
    for _ in range(3):
        await lim.acquire("t", spec)


async def test_fourth_call_refused():
    lim = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=2)
    await lim.acquire("t", spec)
    await lim.acquire("t", spec)
    with pytest.raises(RateLimitedError) as exc_info:
        await lim.acquire("t", spec)
    assert exc_info.value.retry_after_sec > 0
    assert exc_info.value.http_like_status == 429


async def test_refill_after_sleep():
    lim = RateLimiter()
    # 600 per minute = 10 per second → one token back in ~0.1s
    spec = RateLimitSpec(per_minute=600, burst=1)
    await lim.acquire("k", spec)
    with pytest.raises(RateLimitedError):
        await lim.acquire("k", spec)
    await asyncio.sleep(0.15)
    await lim.acquire("k", spec)  # should succeed


async def test_different_keys_independent():
    lim = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=1)
    await lim.acquire("a", spec)
    await lim.acquire("b", spec)  # different key: independent
    with pytest.raises(RateLimitedError):
        await lim.acquire("a", spec)


async def test_gc_removes_idle():
    lim = RateLimiter()
    spec = RateLimitSpec(per_minute=60, burst=1)
    await lim.acquire("idle-key", spec)
    assert "idle-key" in lim._buckets
    # Simulate age by resetting last_access
    lim._buckets["idle-key"].last_access -= 3600
    removed = await lim.gc()
    assert removed >= 1
    assert "idle-key" not in lim._buckets


async def test_concurrent_calls_do_not_overshoot():
    """If burst=5, 20 parallel tasks can acquire at most 5 before refusal."""

    lim = RateLimiter()
    spec = RateLimitSpec(per_minute=0.01, burst=5)  # refill rate negligible

    successes = 0
    failures = 0

    async def one():
        nonlocal successes, failures
        try:
            await lim.acquire("parallel", spec)
            successes += 1
        except RateLimitedError:
            failures += 1

    await asyncio.gather(*[one() for _ in range(20)])
    assert successes == 5
    assert failures == 15
```

### Step 5 — CHANGELOG

```
APPEND CHANGELOG.md

- RFC-004 — Per-tool rate limiting (token bucket, mitigates THREAT T-D1)
```

### Step 6 — verify + full_verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/core/test_rate_limit.py -v
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

6 个测试（Step 4）覆盖：初始 burst / 超限拒绝 / 补回 / key 隔离 / GC / 并发语义。

## Post-checks

- [ ] 7 个测试都绿（6 本 RFC 新增 + 1 full_verify）
- [ ] `git diff --stat` 只列 `files_will_touch`
- [ ] 无既有 tool 的默认行为变化（因为 `rate_limit` 默认 None）
- [ ] 既有 95 passed 数字升到 101 passed

## Rollback plan

见 front-matter。

## Updates to other docs

- `CHANGELOG.md` ✓
- `THREAT_MODEL.md` 的 T-D1 状态 改 `⚠️ partial (in-process only; cross-process TODO)`
- `GAP_ANALYSIS.md` 的 G-S7 改 `PARTIAL (RFC-004 done)`

## Notes for executor

- `_Bucket.lock` 是 asyncio.Lock，不是 threading.Lock。**不要改**。
- 不要把 RateLimiter 存到 RequestContext 里，它是 server 级别全局（multi-tenant 场景才下放）。
- 测试 `test_concurrent_calls_do_not_overshoot` 要求精准，不能删 —— 它保护核心不变量。

## Changelog

- **2026-04-21 初版**
