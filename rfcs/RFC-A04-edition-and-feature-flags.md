---
id: RFC-A04
title: Edition selector and feature flags infrastructure
epic: A-Foundations
status: open
owner: unassigned
role: backend-engineer
blocking_on: [RFC-002]
edition: both
budget:
  max_files_touched: 6
  max_new_files: 4
  max_lines_added: 280
  max_minutes_human: 45
  max_tokens_model: 20000
files_to_read:
  - src/redteam_mcp/config.py
  - src/redteam_mcp/__main__.py
  - src/redteam_mcp/server.py
  - config/default.yaml
files_will_touch:
  - src/redteam_mcp/features.py              # new
  - src/redteam_mcp/editions/__init__.py     # new
  - src/redteam_mcp/editions/pro.py          # new
  - src/redteam_mcp/editions/team.py         # new
  - src/redteam_mcp/config.py                # modified
  - src/redteam_mcp/__main__.py              # modified
  - tests/unit/test_editions.py              # new
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_editions.py -v && .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition pro show-config | findstr /R "edition" && .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition team show-config | findstr /R "edition"
rollback_cmd: |
  git checkout -- src/redteam_mcp/config.py src/redteam_mcp/__main__.py
  if exist src\redteam_mcp\features.py del src\redteam_mcp\features.py
  if exist src\redteam_mcp\editions rmdir /s /q src\redteam_mcp\editions
  if exist tests\unit\test_editions.py del tests\unit\test_editions.py
skill_id: rfc-a04-editions
---

# RFC-A04 — Edition selector and feature flags infrastructure

## Mission

引入 `edition` + `FeatureFlags` 机制，让 Pro / Team 版共享一套代码，通过配置切换行为。

## Context

- PRODUCT_LINES.md 决策 1：采用 **方案 B** Monorepo + Feature Flags。
- 决策 4：Team 版默认关闭 scope / rate limit 等限制，需要**配置层**表达。
- 此 RFC 是 **RFC-T00 Team Unleashed Mode** 和 RFC-T08 Team Bootstrap 的**硬前置**；无它其他 Team RFC 无法启动。
- 不引入任何新功能，**纯基建**。

## Non-goals

- 不实现具体特性（那是 V-/T- 系列的事）。
- 不修改 server.py 的行为 —— 只是把 `edition` 传进来。
- 不加新 CLI 命令（除了 `--edition` 全局开关）。
- 不做 Pro 专属子包（`src/redteam_mcp/pro/`）—— 留给 Pro 第一个 RFC。

## Design

**选定方案**：`FeatureFlags` 是一个 Pydantic model，作为 `Settings.features` 字段存在。`editions/pro.py` 和 `editions/team.py` 各自提供一个 `PRO_DEFAULTS` / `TEAM_DEFAULTS` 实例，CLI 或环境变量 `KESTREL_EDITION` 决定 `Settings` 合并时用哪套 defaults。

**覆盖优先级**（从低到高）：
1. Pro defaults（框架自带）
2. Edition defaults（按 `--edition` 选择覆盖）
3. `config/default.yaml` 的 `features:` 段（用户全局）
4. `~/.kestrel/config.yaml` 的 `features:` 段
5. 项目 `./kestrel.yaml`
6. 环境变量 `REDTEAM_MCP_FEATURES__xxx`
7. CLI `--feature xxx=yes`（最高）

**FeatureFlags 初版字段**（只加 MVP 需要的 6 个，其他留给后续 RFC 逐步加）：

| 字段 | 类型 | Pro 默认 | Team 默认 | 对应 RFC |
|------|------|---------|-----------|---------|
| `scope_enforcement` | `Literal["strict","warn_only","off"]` | `strict` | `warn_only` | RFC-T00 |
| `rate_limit_enabled` | `bool` | `True` | `False` | RFC-T00 |
| `credential_encryption_required` | `bool` | `True` | `False` | RFC-T00 |
| `cost_ledger` | `bool` | `True` | `True` | V-A3 |
| `tool_soft_timeout_enabled` | `bool` | `True` | `False` | V-A2 |
| `untrust_wrap_tool_output` | `bool` | `True` | `True` | V-A4 |

后续 RFC 扩字段不破坏 default（always opt-in via Pydantic 默认值）。

## Steps

### Step 1 — 创建 FeatureFlags

```
WRITE src/redteam_mcp/features.py
"""Feature flags controlling behavior across editions.

Every flag MUST have a default value compatible with Pro edition.
Team edition's `TEAM_DEFAULTS` (see editions/team.py) overrides unsafe-for-prod defaults.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScopeEnforcement = Literal["strict", "warn_only", "off"]


class FeatureFlags(BaseModel):
    """Runtime-toggleable behavior flags. Immutable after Settings load."""

    scope_enforcement: ScopeEnforcement = Field(
        default="strict",
        description="How to handle out-of-scope targets. strict=block, warn_only=log+allow, off=silent",
    )
    rate_limit_enabled: bool = Field(
        default=True,
        description="If False, RateLimiter.acquire() always returns immediately.",
    )
    credential_encryption_required: bool = Field(
        default=True,
        description="If False, CredentialService allows storing plaintext values (Team/local use only).",
    )
    cost_ledger: bool = Field(
        default=True,
        description="If True, every ToolInvocation records estimated cost (tokens + wall seconds).",
    )
    tool_soft_timeout_enabled: bool = Field(
        default=True,
        description="If False, ToolSpec.soft_timeout_sec is ignored (Team: ignore for long ops).",
    )
    untrust_wrap_tool_output: bool = Field(
        default=True,
        description="If True, ToolResult.content is wrapped with <untrusted>...</untrusted> markers before LLM.",
    )

    model_config = {"extra": "forbid", "frozen": True}
```

### Step 2 — 创建 editions 包

```
WRITE src/redteam_mcp/editions/__init__.py
"""Edition presets. Import one via Settings.apply_edition()."""

from redteam_mcp.editions.pro import PRO_DEFAULTS
from redteam_mcp.editions.team import TEAM_DEFAULTS

__all__ = ["PRO_DEFAULTS", "TEAM_DEFAULTS", "get_defaults"]


def get_defaults(edition: str):
    if edition == "pro":
        return PRO_DEFAULTS
    if edition == "team":
        return TEAM_DEFAULTS
    raise ValueError(f"Unknown edition: {edition!r}. Expected 'pro' or 'team'.")
```

```
WRITE src/redteam_mcp/editions/pro.py
"""Pro edition defaults: conservative, compliance-oriented."""

from redteam_mcp.features import FeatureFlags

PRO_DEFAULTS = FeatureFlags()  # all Pydantic defaults = Pro defaults
```

```
WRITE src/redteam_mcp/editions/team.py
"""Team edition defaults: unleashed mode for internal crew.

Decisions baked in per PRODUCT_LINES.md:
- scope_enforcement=warn_only  (crew self-regulates)
- rate_limit_enabled=False     (no throttling during ops)
- credential_encryption_required=False (shared plaintext OK inside vault)
- tool_soft_timeout_enabled=False (long recon is fine)
"""

from redteam_mcp.features import FeatureFlags

TEAM_DEFAULTS = FeatureFlags(
    scope_enforcement="warn_only",
    rate_limit_enabled=False,
    credential_encryption_required=False,
    tool_soft_timeout_enabled=False,
    cost_ledger=True,
    untrust_wrap_tool_output=True,
)
```

### Step 3 — Settings 整合 edition

```
REPLACE src/redteam_mcp/config.py
<<<<<<< SEARCH
class Settings(BaseSettings):
=======
from redteam_mcp.features import FeatureFlags
from redteam_mcp.editions import get_defaults


class Settings(BaseSettings):
>>>>>>> REPLACE
```

在 `Settings` 类里（具体行号由 executor 找），加字段 + 类方法：

```
REPLACE src/redteam_mcp/config.py
<<<<<<< SEARCH
    authorized_scope: Union[list[str], str] = Field(default_factory=list)
=======
    authorized_scope: Union[list[str], str] = Field(default_factory=list)
    edition: Literal["pro", "team"] = Field(default="pro")
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @classmethod
    def build(cls, edition: str | None = None, **overrides) -> "Settings":
        """Build Settings with edition defaults applied before overrides.

        Order: Pro defaults → edition defaults → explicit overrides → env vars.
        """
        import os as _os
        ed = edition or _os.getenv("KESTREL_EDITION") or overrides.pop("edition", None) or "pro"
        base_features = get_defaults(ed).model_dump()
        user_features = overrides.pop("features", {})
        if isinstance(user_features, FeatureFlags):
            user_features = user_features.model_dump(exclude_unset=True)
        merged = {**base_features, **user_features}
        return cls(edition=ed, features=FeatureFlags(**merged), **overrides)
>>>>>>> REPLACE
```

> **Notes for executor**: 上面两处 REPLACE 需要找到现有 `Settings` 类定义的准确位置。如 `from typing import Literal` 没导入，加上它。`Union[list[str], str]` 这行可能在不同位置；用 `grep authorized_scope` 定位。

### Step 4 — CLI 加 `--edition` 全局开关

```
REPLACE src/redteam_mcp/__main__.py
<<<<<<< SEARCH
app = typer.Typer(help="Red Team MCP server CLI")
=======
app = typer.Typer(help="Red Team MCP server CLI")


_edition_state = {"value": None}


@app.callback()
def _global(
    edition: str = typer.Option(
        None,
        "--edition",
        help="Which edition preset to load: 'pro' (default) or 'team'.",
        envvar="KESTREL_EDITION",
    ),
):
    _edition_state["value"] = edition
>>>>>>> REPLACE
```

所有已存在的命令若调用 `Settings()` 或 `Settings.model_validate(...)` 的，改为 `Settings.build(edition=_edition_state["value"])`。executor 逐个找替换。

加新命令 `show-config`：

```
REPLACE src/redteam_mcp/__main__.py
<<<<<<< SEARCH
if __name__ == "__main__":
    app()
=======
@app.command("show-config")
def show_config_cmd() -> None:
    """Print resolved Settings (edition + features) as JSON."""
    import json
    s = Settings.build(edition=_edition_state["value"])
    print(json.dumps({"edition": s.edition, "features": s.features.model_dump()}, indent=2))


if __name__ == "__main__":
    app()
>>>>>>> REPLACE
```

### Step 5 — 测试

```
WRITE tests/unit/test_editions.py
from __future__ import annotations

import pytest

from redteam_mcp.config import Settings
from redteam_mcp.editions import PRO_DEFAULTS, TEAM_DEFAULTS, get_defaults
from redteam_mcp.features import FeatureFlags


def test_feature_flags_frozen():
    ff = FeatureFlags()
    with pytest.raises(Exception):
        ff.rate_limit_enabled = False  # frozen


def test_pro_defaults_are_strict():
    assert PRO_DEFAULTS.scope_enforcement == "strict"
    assert PRO_DEFAULTS.rate_limit_enabled is True
    assert PRO_DEFAULTS.credential_encryption_required is True


def test_team_defaults_are_unleashed():
    assert TEAM_DEFAULTS.scope_enforcement == "warn_only"
    assert TEAM_DEFAULTS.rate_limit_enabled is False
    assert TEAM_DEFAULTS.credential_encryption_required is False
    assert TEAM_DEFAULTS.tool_soft_timeout_enabled is False


def test_get_defaults_unknown_edition_raises():
    with pytest.raises(ValueError):
        get_defaults("enterprise")


def test_settings_build_pro_default():
    s = Settings.build()
    assert s.edition == "pro"
    assert s.features.scope_enforcement == "strict"


def test_settings_build_team():
    s = Settings.build(edition="team")
    assert s.edition == "team"
    assert s.features.scope_enforcement == "warn_only"
    assert s.features.rate_limit_enabled is False


def test_settings_build_env_overrides(monkeypatch):
    monkeypatch.setenv("KESTREL_EDITION", "team")
    s = Settings.build()
    assert s.edition == "team"
    assert s.features.scope_enforcement == "warn_only"


def test_settings_build_explicit_feature_overrides():
    from redteam_mcp.features import FeatureFlags as FF
    s = Settings.build(edition="team", features=FF(scope_enforcement="strict"))
    assert s.features.scope_enforcement == "strict"  # explicit wins
    assert s.features.rate_limit_enabled is False   # team default preserved
```

### Step 6 — 运行验证

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/test_editions.py -v
RUN .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition pro show-config
RUN .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition team show-config
```

## Tests

见 Step 5。**8 个测试覆盖**：
- Pydantic frozen
- Pro/Team defaults
- 未知 edition 抛错
- Settings.build 默认 / edition 参数 / 环境变量 / 显式 overrides

## Post-checks

- [ ] `git diff --stat` 只列出 `files_will_touch` 里的 7 个文件
- [ ] `pytest tests/unit/test_editions.py` 8 passed
- [ ] `show-config --edition pro` 输出 `"scope_enforcement": "strict"`
- [ ] `show-config --edition team` 输出 `"scope_enforcement": "warn_only"`
- [ ] 老 pytest 套件仍 95 passed（未破坏现有行为）

## Rollback plan

```
git checkout -- src/redteam_mcp/config.py src/redteam_mcp/__main__.py
rmdir /s /q src\redteam_mcp\editions
del src\redteam_mcp\features.py tests\unit\test_editions.py
```

无 DB 副作用，零 migration。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加 `RFC-A04 closes feature flags infrastructure`
- `PRODUCT_LINES.md` → 无改动（已含决策）
- `AUDIT_V2.md` → Part 8 标 V- 系列依赖项已就绪
- `rfcs/INDEX.md` → RFC-A04 标 `done`，新增 Epic T 并把 RFC-T00/T08 标 unblocked

## Notes for executor

- `pydantic.BaseModel(frozen=True)` 使对象不可变 —— 测试里 `ff.rate_limit_enabled = False` 会抛 `ValidationError` 或 `FrozenInstanceError`，用 `pytest.raises(Exception)` 保险。
- `Literal["pro", "team"]` 在 Python 3.11+ 的 `typing` 模块；`typing_extensions` fallback 可忽略（项目已 3.12）。
- `Settings.build` 的实现用 `**overrides` 传递，`features=` 若传 `FeatureFlags` 实例要 `model_dump(exclude_unset=True)` 以保留显式字段语义。
- `_edition_state` 全局字典是 Typer 的推荐模式（callback 不方便返回值到命令）。
- 若 `config.py` 里已有 `from typing import Literal`，不要重复导入。

## Changelog

- **2026-04-21 初版** by AI — based on PRODUCT_LINES.md decision 1
