"""In-process token-bucket rate limiter.

Used by the MCP server dispatcher to throttle per-(tool, engagement) call
rates, mitigating THREAT T-D1 (runaway tool calls).

Design constraints
------------------

* Zero external dependencies (no Redis, no files).
* Async-safe via an ``asyncio.Lock`` per bucket.
* Monotonic clock to avoid wall-clock jumps.
* Buckets GC themselves after inactivity so long-running servers do not
  accumulate unbounded per-engagement state.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Hashable
from dataclasses import dataclass, field

from ..core_errors import KestrelError

_GC_INACTIVITY_SEC = 600.0


class RateLimitedError(KestrelError):
    """Raised when a token bucket has no token available for immediate use."""

    error_code = "kestrel.rate_limited"
    user_actionable = True
    http_like_status = 429

    def __init__(self, key: Hashable, retry_after_sec: float) -> None:
        rounded = max(retry_after_sec, 0.0)
        super().__init__(
            f"Rate limit exceeded for {key!r}. Retry after {rounded:.1f}s.",
            key=repr(key),
            retry_after_sec=rounded,
        )
        self.retry_after_sec = rounded


@dataclass(frozen=True)
class RateLimitSpec:
    """Declared on a ToolSpec; controls the token bucket shape."""

    per_minute: float
    burst: int = 1

    def __post_init__(self) -> None:
        if self.per_minute <= 0:
            raise ValueError("per_minute must be > 0")
        if self.burst <= 0:
            raise ValueError("burst must be > 0")


@dataclass
class _Bucket:
    capacity: int
    refill_rate_per_sec: float
    tokens: float
    last_refill: float
    last_access: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RateLimiter:
    """Process-wide registry of per-key token buckets."""

    def __init__(self) -> None:
        self._buckets: dict[Hashable, _Bucket] = {}
        self._registry_lock = asyncio.Lock()

    async def acquire(self, key: Hashable, spec: RateLimitSpec) -> None:
        """Consume one token or raise :class:`RateLimitedError`."""

        now = time.monotonic()
        refill_rate = spec.per_minute / 60.0

        async with self._registry_lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(
                    capacity=spec.burst,
                    refill_rate_per_sec=refill_rate,
                    tokens=float(spec.burst),
                    last_refill=now,
                    last_access=now,
                )
                self._buckets[key] = bucket
            else:
                bucket.capacity = spec.burst
                bucket.refill_rate_per_sec = refill_rate
                bucket.tokens = min(bucket.tokens, float(spec.burst))
                bucket.last_access = now

        async with bucket.lock:
            self._refill(bucket)
            bucket.last_access = time.monotonic()
            if bucket.tokens < 1.0:
                deficit = 1.0 - bucket.tokens
                retry_after = deficit / bucket.refill_rate_per_sec
                raise RateLimitedError(key, retry_after)
            bucket.tokens -= 1.0

    def _refill(self, bucket: _Bucket) -> None:
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        if elapsed <= 0:
            return
        bucket.tokens = min(
            float(bucket.capacity),
            bucket.tokens + elapsed * bucket.refill_rate_per_sec,
        )
        bucket.last_refill = now

    async def gc(self) -> int:
        """Drop buckets idle for longer than the inactivity threshold."""

        now = time.monotonic()
        async with self._registry_lock:
            to_remove = [
                key
                for key, bucket in self._buckets.items()
                if now - bucket.last_access > _GC_INACTIVITY_SEC
            ]
            for key in to_remove:
                self._buckets.pop(key, None)
        return len(to_remove)


__all__ = ["RateLimitedError", "RateLimiter", "RateLimitSpec"]
