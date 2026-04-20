---
id: RFC-A04
title: Edition selector and feature flags infrastructure
epic: A-Foundations
status: done
owner: unassigned
role: backend-engineer
blocking_on: []
edition: both
budget:
  max_files_touched: 7
  max_new_files: 5
  max_lines_added: 260
  max_minutes_human: 45
  max_tokens_model: 20000
files_to_read:
  - src/redteam_mcp/config.py
  - src/redteam_mcp/__main__.py
files_will_touch:
  - src/redteam_mcp/features.py              # new
  - src/redteam_mcp/editions/__init__.py     # new
  - src/redteam_mcp/editions/pro.py          # new
  - src/redteam_mcp/editions/team.py         # new
  - src/redteam_mcp/config.py                # modified
  - src/redteam_mcp/__main__.py              # modified
  - tests/unit/test_editions.py              # new
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_editions.py -v
rollback_cmd: |
  git checkout -- src/redteam_mcp/config.py src/redteam_mcp/__main__.py
  if exist src\redteam_mcp\features.py del src\redteam_mcp\features.py
  if exist src\redteam_mcp\editions rmdir /s /q src\redteam_mcp\editions
  if exist tests\unit\test_editions.py del tests\unit\test_editions.py
skill_id: rfc-a04-editions
---

# RFC-A04 — Edition selector and feature flags infrastructure

## Mission

引入 `--edition pro|team` 选择 + `FeatureFlags` 基建，Pro/Team 共享一套代码。

## Context

- PRODUCT_LINES.md 决策 1：monorepo + feature flags 分叉策略。
- 是 RFC-T00 / T08 的硬前置；但 **本 RFC 只做基建**，不碰 server.py、不碰
  security.py、不改任何运行时行为 —— 设置加了新字段 `edition` / `features`，默
  认值与旧 Pro 行为等价。
- 已通过 `validate_rfc.py` 预检。SEARCH 块全部从真实 `src/redteam_mcp/config.py`
  和 `src/redteam_mcp/__main__.py` 复制（2026-04-21 审计后重写，见
  RFC_AUDIT_PREFLIGHT.md）。

## Non-goals

- 不实现任何 feature flag 的具体行为（那是 RFC-T00 / V- 系列的事）。
- 不改 server.py、security.py、rate_limit.py —— 本 RFC 完成后 Pro 行为不变。
- 不加 Pro 专属子包 `src/redteam_mcp/pro/` —— 那是 Pro 第一个 RFC 的事。
- 不实现 `~/.kestrel/config.yaml` 读取（目前只支持 env + CLI，Pro 第一版 config
  先沿用现有的 `~/.redteam-mcp/config.yaml` 通道）。

## Design

6 个 FeatureFlags 字段 — 只挑 MVP 需要的，其他后续 RFC 逐个加：

| 字段 | Pro 默认 | Team 默认 | 归属 RFC（消费者） |
|------|---------|-----------|---------------------|
| `scope_enforcement` | `"strict"` | `"warn_only"` | RFC-T00 |
| `rate_limit_enabled` | `True` | `False` | RFC-T00b (待写) |
| `credential_encryption_required` | `True` | `False` | RFC-003 消费 |
| `cost_ledger` | `True` | `True` | RFC-V07 |
| `tool_soft_timeout_enabled` | `True` | `False` | RFC-V06 |
| `untrust_wrap_tool_output` | `True` | `True` | RFC-V08 |

字段是 `frozen=True` 的 Pydantic model — 启动后不可变。

CLI 入口：顶层 `--edition` option 作为 `_root` callback 的新参数（**合并**到
现有 callback，不加独立 callback），加 `show-config` 子命令打印解析结果。

## Steps

### Step 1 — 新建 features.py

```
WRITE src/redteam_mcp/features.py
```
```python
"""Feature flags controlling runtime behavior across editions.

Every flag has a default compatible with Pro (strict) edition. Team edition's
``TEAM_DEFAULTS`` (see ``editions/team.py``) overrides the unsafe-for-prod
defaults.

See PRODUCT_LINES.md Part 9 for the decisions baked in here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ScopeEnforcement = Literal["strict", "warn_only", "off"]


class FeatureFlags(BaseModel):
    """Runtime-toggleable behavior flags. Immutable after Settings load."""

    scope_enforcement: ScopeEnforcement = Field(
        default="strict",
        description="How to handle out-of-scope targets. "
                    "strict=block, warn_only=log+allow, off=silent.",
    )
    rate_limit_enabled: bool = Field(
        default=True,
        description="If False, RateLimiter.acquire() is a no-op.",
    )
    credential_encryption_required: bool = Field(
        default=True,
        description="If False, CredentialService allows plaintext values.",
    )
    cost_ledger: bool = Field(
        default=True,
        description="If True, record estimated cost per ToolInvocation.",
    )
    tool_soft_timeout_enabled: bool = Field(
        default=True,
        description="If False, ToolSpec.soft_timeout_sec is ignored.",
    )
    untrust_wrap_tool_output: bool = Field(
        default=True,
        description="If True, wrap ToolResult with <untrusted>...</untrusted>.",
    )

    model_config = {"extra": "forbid", "frozen": True}
```

### Step 2 — 新建 editions 包

```
WRITE src/redteam_mcp/editions/__init__.py
```
```python
"""Edition presets for feature flags.

``get_defaults(name)`` returns the ``FeatureFlags`` instance appropriate for
the given edition. Used by ``Settings.build()``.
"""

from __future__ import annotations

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

### Step 3 — Pro defaults

```
WRITE src/redteam_mcp/editions/pro.py
```
```python
"""Pro edition defaults: conservative, compliance-oriented."""

from __future__ import annotations

from redteam_mcp.features import FeatureFlags

PRO_DEFAULTS = FeatureFlags()  # all Pydantic defaults = Pro defaults
```

### Step 4 — Team defaults

```
WRITE src/redteam_mcp/editions/team.py
```
```python
"""Team edition defaults: unleashed mode for internal crew.

Decisions (see PRODUCT_LINES.md Part 9):
- scope_enforcement=warn_only  (crew self-regulates)
- rate_limit_enabled=False     (no throttling during ops)
- credential_encryption_required=False (shared plaintext OK inside vault)
- tool_soft_timeout_enabled=False (long recon is fine)
"""

from __future__ import annotations

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

### Step 5 — config.py: 加 Literal import + FeatureFlags import + 2 字段 + build()

**5a** — 加 `Literal` 到 typing import.

```
REPLACE src/redteam_mcp/config.py
<<<<<<< SEARCH
from typing import Any
=======
from typing import Any, Literal
>>>>>>> REPLACE
```

**5b** — 加 FeatureFlags import 在 pydantic-settings 后.

```
REPLACE src/redteam_mcp/config.py
<<<<<<< SEARCH
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
=======
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .features import FeatureFlags
>>>>>>> REPLACE
```

**5c** — 加两个字段 + `build()` classmethod 到 `Settings` 类.

```
REPLACE src/redteam_mcp/config.py
<<<<<<< SEARCH
    server: ServerMeta = Field(default_factory=ServerMeta)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)

    @classmethod
    def settings_customise_sources(
=======
    server: ServerMeta = Field(default_factory=ServerMeta)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    edition: Literal["pro", "team"] = Field(default="pro")
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    @classmethod
    def build(cls, edition: str | None = None, **overrides: Any) -> "Settings":
        """Build Settings with edition defaults applied before overrides.

        Order of precedence: Pro defaults -> edition defaults -> explicit
        overrides -> env vars (handled by settings_customise_sources).
        """

        from .editions import get_defaults

        ed = edition or os.getenv("KESTREL_EDITION") or overrides.pop("edition", None) or "pro"
        base_features = get_defaults(ed).model_dump()
        user_features = overrides.pop("features", {})
        if isinstance(user_features, FeatureFlags):
            user_features = user_features.model_dump(exclude_unset=True)
        merged = {**base_features, **user_features}
        return cls(edition=ed, features=FeatureFlags(**merged), **overrides)

    @classmethod
    def settings_customise_sources(
>>>>>>> REPLACE
```

### Step 6 — __main__.py: 加全局 --edition option + show-config

**6a** — 合并 `--edition` 参数进现有 `_root` callback.

```
REPLACE src/redteam_mcp/__main__.py
<<<<<<< SEARCH
@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)
=======
_edition_state: dict[str, str | None] = {"value": None}


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    edition: Annotated[
        str | None,
        typer.Option(
            "--edition",
            help="Edition preset to load: 'pro' (default) or 'team'.",
            envvar="KESTREL_EDITION",
        ),
    ] = None,
) -> None:
    _edition_state["value"] = edition
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)
>>>>>>> REPLACE
```

**6b** — 加 `show-config` 命令在 `version` 之前.

```
REPLACE src/redteam_mcp/__main__.py
<<<<<<< SEARCH
@app.command()
def version() -> None:
    """Print the installed version."""

    typer.echo(__version__)
=======
@app.command("show-config")
def show_config_cmd() -> None:
    """Print resolved Settings (edition + features) as JSON."""

    from .config import Settings

    s = Settings.build(edition=_edition_state["value"])
    payload = {"edition": s.edition, "features": s.features.model_dump()}
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def version() -> None:
    """Print the installed version."""

    typer.echo(__version__)
>>>>>>> REPLACE
```

### Step 7 — 测试

```
WRITE tests/unit/test_editions.py
```
```python
"""Tests for RFC-A04 edition + FeatureFlags infrastructure."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from redteam_mcp.config import Settings
from redteam_mcp.editions import PRO_DEFAULTS, TEAM_DEFAULTS, get_defaults
from redteam_mcp.features import FeatureFlags


def test_feature_flags_frozen():
    ff = FeatureFlags()
    with pytest.raises((ValidationError, TypeError)):
        ff.rate_limit_enabled = False


def test_feature_flags_extra_forbidden():
    with pytest.raises(ValidationError):
        FeatureFlags(unknown_flag=True)  # type: ignore[call-arg]


def test_pro_defaults_are_strict():
    assert PRO_DEFAULTS.scope_enforcement == "strict"
    assert PRO_DEFAULTS.rate_limit_enabled is True
    assert PRO_DEFAULTS.credential_encryption_required is True
    assert PRO_DEFAULTS.tool_soft_timeout_enabled is True


def test_team_defaults_are_unleashed():
    assert TEAM_DEFAULTS.scope_enforcement == "warn_only"
    assert TEAM_DEFAULTS.rate_limit_enabled is False
    assert TEAM_DEFAULTS.credential_encryption_required is False
    assert TEAM_DEFAULTS.tool_soft_timeout_enabled is False
    assert TEAM_DEFAULTS.cost_ledger is True
    assert TEAM_DEFAULTS.untrust_wrap_tool_output is True


def test_get_defaults_unknown_edition_raises():
    with pytest.raises(ValueError):
        get_defaults("enterprise")


def test_settings_build_pro_is_default():
    s = Settings.build()
    assert s.edition == "pro"
    assert s.features.scope_enforcement == "strict"
    assert s.features.rate_limit_enabled is True


def test_settings_build_team():
    s = Settings.build(edition="team")
    assert s.edition == "team"
    assert s.features.scope_enforcement == "warn_only"
    assert s.features.rate_limit_enabled is False


def test_settings_build_env_override(monkeypatch):
    monkeypatch.setenv("KESTREL_EDITION", "team")
    s = Settings.build()
    assert s.edition == "team"
    assert s.features.scope_enforcement == "warn_only"


def test_settings_build_explicit_feature_override_wins():
    explicit = FeatureFlags(scope_enforcement="strict")
    s = Settings.build(edition="team", features=explicit)
    # Explicit override wins for the field it sets...
    assert s.features.scope_enforcement == "strict"
    # ...but other Team defaults are preserved.
    assert s.features.rate_limit_enabled is False


def test_settings_edition_field_rejects_unknown():
    # pydantic Literal["pro", "team"] rejects other values.
    with pytest.raises(ValidationError):
        Settings(edition="enterprise")  # type: ignore[arg-type]
```

### Step 8 — 运行验证

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/test_editions.py -v
```

### Step 9 — 回归

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

## Tests

Step 7 含 10 个测试：
- Pydantic frozen + extra=forbid
- Pro / Team defaults 全字段检查
- `get_defaults` 未知 edition 抛错
- `Settings.build` 默认 / `edition=` 参数 / 环境变量 / 显式 FeatureFlags 覆盖
- `Settings.edition` Literal 拒绝未知值

## Post-checks

- [ ] `git diff --stat` 只列 `files_will_touch` 里的 7 个文件
- [ ] `pytest tests/unit/test_editions.py` 10 passed
- [ ] `.venv\Scripts\python.exe -m redteam_mcp show-config` 输出
      `{"edition": "pro", "features": {...}}`，`scope_enforcement: "strict"`
- [ ] `.venv\Scripts\python.exe -m redteam_mcp --edition team show-config`
      输出 `scope_enforcement: "warn_only"`
- [ ] `$env:KESTREL_EDITION = "team"; .venv\Scripts\python.exe -m redteam_mcp
      show-config` 同样显示 warn_only（随后 `Remove-Item Env:KESTREL_EDITION`）
- [ ] 原有 95 passed 测试仍然绿（本 RFC 不改运行时行为）

## Rollback plan

见 front-matter `rollback_cmd`。没有 DB/迁移副作用。

## Updates to other docs

- `CHANGELOG.md` → `[Unreleased]` 加 `RFC-A04 closes edition + feature flags
  infrastructure`
- `rfcs/INDEX.md` → RFC-A04 状态改 `done`，解锁 RFC-T00 (仍在
  `spec_needs_rewrite`)
- 不改 `AUDIT_V2.md`（V- 系列消费者 RFC 各自更新）

## Notes for executor

- **PEP 621 / PEP 735**: 本 RFC 不加 `[tool.uv] default-groups`（那指向
  PEP 735 不存在的表）。参考 RFC-001 v1.1 的修复。
- **`_root` 合并**: Step 6a **不要** 新加一个 `@app.callback`；现有 `_root`
  是唯一 callback，只能往它里面加参数。添加两个 callback 会让 Typer 的 help
  输出异常。
- **Pydantic frozen**: `FeatureFlags` 用 `model_config = {"frozen": True}`，
  尝试设置字段会抛 `ValidationError`（v2）或 `TypeError`（v1 兼容）。测试用
  `pytest.raises((ValidationError, TypeError))` 兼容两路径。
- **env 变量名**: 本 RFC 用 `KESTREL_EDITION`（不带 `REDTEAM_MCP_` 前缀），因为
  它是 CLI-level switch，不通过 pydantic-settings 读；`Settings.build()` 里
  `os.getenv("KESTREL_EDITION")` 直接读。
- **CLI 验证**: Typer 顶层 callback 的 option 要加在**同一个** `_root` 上，不能另开
  一个。Typer 仅支持一个 `invoke_without_command=True` callback。
- **Literal["pro","team"]**: Python 3.10+ 有原生 `Literal`；本项目 3.12 下无需
  `typing_extensions` 回退。
- **不 lazy import `FeatureFlags`**: Step 5b 加的顶层 import 是必要的，因为
  `Field(default_factory=FeatureFlags)` 需要运行时类引用；`from __future__ import
  annotations` 只懒化类型注解，不懒化函数参数的默认值计算。

## Changelog

- **2026-04-21 v1.0** — Initial spec (failed pre-flight with 2 SEARCH
  hallucinations).
- **2026-04-21 v2.0** — **Full rewrite** after RFC_AUDIT_PREFLIGHT.md. Every
  SEARCH block now copied from real files. 6 FeatureFlags fields only (MVP
  subset). Passes `validate_rfc.py`. Budget: 260 lines (down from 280).
