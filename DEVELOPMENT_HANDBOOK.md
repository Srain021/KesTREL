# DEVELOPMENT HANDBOOK

> 本文档是 maintainer 和 contributor 的强制阅读材料。
> 所有规范都必须可执行、可自动化、能被 CI 强制。
> 所有决定都有参考源（RFC / 标准 / 权威文档）。

**Version**: 1.0
**Applies to**: kestrel-mcp core, all plugins, all tool wrappers

---

## 目录

1. [目录结构规范](#1-目录结构规范)
2. [Git 工作流](#2-git-工作流)
3. [Commit 规范](#3-commit-规范)
4. [Branch 策略](#4-branch-策略)
5. [Pull Request 规范](#5-pull-request-规范)
6. [Code Review 规范](#6-code-review-规范)
7. [代码风格](#7-代码风格)
8. [类型系统](#8-类型系统)
9. [错误处理标准](#9-错误处理标准)
10. [日志与可观测性规范](#10-日志与可观测性规范)
11. [测试规范](#11-测试规范)
12. [依赖管理](#12-依赖管理)
13. [架构决策记录（ADR）](#13-架构决策记录adr)
14. [Release 流程](#14-release-流程)
15. [安全开发流程](#15-安全开发流程)
16. [新 Tool 贡献流程](#16-新-tool-贡献流程)
17. [Plugin 开发契约](#17-plugin-开发契约)
18. [调试指南](#18-调试指南)
19. [性能规范](#19-性能规范)
20. [文档规范](#20-文档规范)

---

## 1. 目录结构规范

```
kestrel-mcp/
├── .github/                   # GitHub 配置
├── docs/                      # 用户文档源（MkDocs）
├── examples/                  # 示例配置与插件
├── scripts/                   # 一次性或辅助脚本（非运行时）
├── src/kestrel_mcp/           # Python 源码（单 package）
│   ├── core/                  # 框架核心，不依赖 tool
│   ├── domain/                # 领域模型（G-P1）
│   ├── tools/                 # 官方 tool modules
│   ├── workflows/             # 跨 tool 工作流
│   ├── plugins/               # plugin 加载框架
│   ├── cli/                   # CLI 命令
│   └── telemetry/             # metrics / logs / traces
├── tests/
│   ├── unit/                  # 快速，mock IO
│   ├── integration/           # 真 subprocess / 真 container
│   ├── e2e/                   # 完整 LLM → MCP → tool 回路
│   └── contract/              # JSON Schema 契约
├── benchmarks/                # pytest-benchmark
├── plugins-official/          # 一方 plugin（可选安装）
└── [根级文档，见下]
```

### 根级文档（按重要性）

| 文件 | 作用 | 强制 |
|------|------|------|
| README.md | 入口 | ✅ |
| LICENSE | Apache 2.0 原文 | ✅ |
| NOTICE | Apache 归属声明 | ✅ |
| RESPONSIBLE_USE.md | 负责任使用条款 | ✅ |
| SECURITY.md | 漏洞披露流程 | ✅（GitHub 要求） |
| CODE_OF_CONDUCT.md | Contributor Covenant v2.1 | ✅ |
| CONTRIBUTING.md | 贡献指南 | ✅ |
| CHANGELOG.md | Keep a Changelog 格式 | ✅ |
| CODEOWNERS | 路径 → owner 映射 | ✅ |
| MASTER_PLAN.md | 项目路线图 | 内部 |
| GAP_ANALYSIS.md | 工程缺陷清单 | 内部 |
| DEVELOPMENT_HANDBOOK.md | 本文档 | ✅ |
| ARCHITECTURE.md | 架构决策摘要 | ✅ |

### 禁止

- ❌ 根目录放 `.py` 脚本
- ❌ `tests/` 引用 `scripts/`
- ❌ `core/` 引用 `tools/`（单向依赖）
- ❌ `tools/` 相互 import（通过 core 交互）

---

## 2. Git 工作流

**采用 GitHub Flow**（简单版 git flow），非 gitflow。

```
main                永远可发布
└─ feat/<name>      功能分支
└─ fix/<name>       bug 修复
└─ chore/<name>     杂项
└─ docs/<name>      纯文档
└─ release/vX.Y.Z   发布冻结（仅 maintainer）
```

**流程**:
1. 从 `main` 切出 `feat/xxx`
2. 本地提交（commit 规范见下）
3. 推到 fork
4. 开 PR 到 upstream `main`
5. CI 绿 + 1+ approve 后 maintainer merge（squash 策略）
6. 分支自动删除

**禁止**:
- Force push 到 `main`
- Merge commit 合进 `main`（用 squash 或 rebase）
- 超过 500 行 diff 的 PR（拆小）

---

## 3. Commit 规范

**Conventional Commits 1.0.0**。格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type** 枚举：
- `feat` 新功能
- `fix` bug 修复
- `docs` 仅文档
- `style` 格式（不影响代码运行）
- `refactor` 重构（无功能变化）
- `perf` 性能优化
- `test` 新增 / 修正测试
- `chore` 构建 / 工具链
- `security` 安全相关修复
- `breaking` 破坏性变更

**scope** 建议值：`core`, `tools.nuclei`, `cli`, `docs`, `ci`, `deps`

**示例**:
```
feat(tools.subfinder): add subfinder_enum tool

Implement passive subdomain enumeration using upstream v2.6.3.
Supports all_sources flag and recursive mode.

Refs: #42
```

**Breaking change 示例**:
```
feat(core)!: rename ToolSpec.dangerous to ToolSpec.requires_ack

BREAKING CHANGE: `ToolSpec.dangerous` removed, use `requires_ack` instead.
All plugin authors must update. Migration: rename attribute.

Refs: ADR-004
```

**CI 强制**: `commitlint.config.js` + pre-commit hook + GitHub Action。
不规范的 commit 会被 CI block 到 PR。

**Sign-off**（DCO 可选，项目未要求 CLA 时用这个）:
```
git commit -s -m "..."
```

---

## 4. Branch 策略

### `main` 保护规则

在 GitHub Settings → Branch Protection:

- ✅ Require pull request reviews before merging: **1+ approval**
- ✅ Require status checks: `ci / lint`, `ci / test (ubuntu-latest, 3.12)`, `ci / security`
- ✅ Require branches to be up to date
- ✅ Require signed commits
- ✅ Include administrators
- ✅ Restrict force pushes
- ✅ Restrict deletions

### Release branches

仅在发布前冻结：
```
release/v1.2.0
```
只接受 `fix`, `docs` commits。发布后立即删除，tag 保留。

---

## 5. Pull Request 规范

### PR 标题
同 Commit 规范 subject。

### PR 描述模板

`.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## 变更内容
<!-- 简述 what & why，不要 copy commit log -->

## 相关 Issue
<!-- Fixes #123 -->

## 类型
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Docs
- [ ] Refactor / chore

## 检查清单
- [ ] 代码通过 `ruff check` / `ruff format --check` / `mypy --strict`
- [ ] 新增 / 修改代码有单测，覆盖率未下降
- [ ] 如新增 tool：遵循 §16 贡献流程
- [ ] 如改动 public API：更新 CHANGELOG 和迁移指南
- [ ] 如引入新依赖：license 兼容 Apache 2.0，记录在 ADR
- [ ] 如涉及安全：已在 threat model 中分析

## 如何测试
<!-- Reviewer 手动验证步骤 -->

## 截图 / 输出
<!-- 可选 -->
```

### PR 生命周期

```
Draft → Ready → Review requested
  → Changes requested → Fix → ...
  → Approved → Merge（maintainer）
```

**SLA**:
- Review 开始: 3 工作日内
- 第一轮反馈完成: 5 工作日
- 超过 14 天无活动的 PR: 自动 stale → 30 天后关闭

---

## 6. Code Review 规范

**Reviewer 职责**:
1. 正确性 — 代码做了它说的事吗
2. 可读性 — 6 个月后你能读懂吗
3. 测试 — 边界条件覆盖了吗
4. 性能 — 有明显热点吗
5. 安全 — 引入新攻击面了吗
6. 依赖 — 是否必要、是否兼容

**禁忌**:
- ❌ "nit: xxx"（小问题不该 block PR）
- ❌ 要求作者改风格（自动化的事）
- ❌ 不给理由的否决

**Approve 不等于 Merge**。Approve 意味着"我看过、我负责"。
Merge 是 maintainer 的决定。

**Conflict resolution**:
Reviewer 和作者有分歧时：
1. 讨论 → 若无果
2. 拉第二个 reviewer
3. 升级到 CODEOWNERS 决定
4. 实在不行升级到 maintainer 会议（月度）

---

## 7. 代码风格

### 强制工具

| 工具 | 配置 | 用途 |
|------|------|------|
| **ruff** | `pyproject.toml` | lint + format（替代 black/isort/flake8） |
| **mypy** | `pyproject.toml` | 类型检查（strict mode） |
| **bandit** | `pyproject.toml` | 安全 lint |
| **semgrep** | `.semgrep.yml` | 自定义规则 |
| **vulture** | 可选 | 死代码检测 |

### ruff 配置（示范）

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort
    "W",    # warnings
    "UP",   # pyupgrade
    "N",    # naming
    "B",    # bugbear
    "SIM",  # simplify
    "C90",  # mccabe complexity
    "RUF",  # ruff-specific
    "S",    # bandit（基础）
    "BLE",  # no bare except
    "DTZ",  # datetime 必须带 tz
    "EM",   # error message 规范
    "ISC",  # implicit string concat
    "ICN",  # import conventions
    "PIE",  # misc
    "PL",   # pylint（子集）
    "PT",   # pytest style
    "Q",    # quotes
    "RSE",  # raise
    "RET",  # return
    "SLF",  # self._private
    "T20",  # no print
    "TID",  # tidy imports
]
ignore = [
    "E501",  # handled by formatter
    "S101",  # pytest assert 允许
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["SLF", "PLR2004", "S106"]
```

### 命名

- 类 `PascalCase`
- 函数 / 变量 `snake_case`
- 常量 `UPPER_SNAKE`
- 私有 `_prefix`
- 真正的内部 `__double_prefix`（少用，仅防名字冲突）
- Tool ID 全小写下划线：`shodan_search` 不要 `shodanSearch`

### 注释

- **docstring** 用 **Google style**（和 `sphinx-napoleon` 配合）
- 不在代码里写显而易见的注释（`i += 1  # 增加 i`）
- TODO 必须带 owner + issue link：`# TODO(@you, #42): 处理 IPv6`

### 最大复杂度

- McCabe C90 complexity ≤ 10
- 函数行数 ≤ 50
- 文件行数 ≤ 500
- 嵌套深度 ≤ 4

超过 → CI 失败 → 拆解。

---

## 8. 类型系统

### 强制 mypy strict

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
check_untyped_defs = true
no_implicit_optional = true
plugins = ["pydantic.mypy"]
```

### 类型规范

- ✅ 所有 public 函数参数 + 返回类型必须有
- ✅ 使用 `from __future__ import annotations`（延迟求值）
- ✅ `Optional[X]` 用 `X | None`（Python 3.10+）
- ✅ 容器用具体类型：`list[int]` 而非 `List[int]`
- ✅ Protocol / TypedDict > 裸 dict
- ❌ 不用 `Any`，除非注释说明原因
- ❌ 不用 `# type: ignore`，除非有 comment

### Pydantic 用法

- ✅ 所有 MCP tool input schema 来自 Pydantic model（而非手写 JSON Schema）
- ✅ `model_config = ConfigDict(frozen=True)` 能 frozen 就 frozen
- ✅ `Field(..., description="...")` 必填以供 schema 文档化

---

## 9. 错误处理标准

### 异常层级

```python
# src/kestrel_mcp/core/errors.py

class KestrelError(Exception):
    """Base class for all kestrel-specific exceptions."""

    error_code: str = "kestrel.generic"
    user_actionable: bool = False
    http_like_status: int = 500


# 4xx 用户相关（用户可修正）
class UserInputError(KestrelError):
    error_code = "kestrel.user_input"
    user_actionable = True
    http_like_status = 400

class AuthorizationError(KestrelError):
    error_code = "kestrel.authorization"
    user_actionable = True
    http_like_status = 403

class ResourceNotFoundError(KestrelError):
    error_code = "kestrel.not_found"
    user_actionable = True
    http_like_status = 404


# 5xx 系统相关
class ToolExecutionError(KestrelError):
    error_code = "kestrel.tool_execution"
    http_like_status = 500

class ExternalServiceError(KestrelError):
    """Upstream API failed (Shodan, GitHub, etc)."""
    error_code = "kestrel.external_service"
    http_like_status = 502

class InternalError(KestrelError):
    """Bug in kestrel-mcp itself."""
    error_code = "kestrel.internal"
    http_like_status = 500
```

### 规范

- ❌ `except Exception:` 没有 explicit re-raise
- ❌ `raise Exception("...")` 裸异常
- ✅ 特定异常类型
- ✅ 用 `logger.exception()` 不丢 stack
- ✅ 用户错误的消息明确告诉"怎么修"

### ToolResult 约定

```python
# 成功
return ToolResult(text="...", structured={...})

# 用户错误（他能修）
return ToolResult.error(
    "Query is too long (max 1024 chars). Got 2048.",
    error_code="kestrel.user_input",
)

# 系统错误
raise ToolExecutionError(f"nuclei exited with {code}")
# 服务器统一把异常转 ToolResult
```

---

## 10. 日志与可观测性规范

### 三支柱

| 支柱 | 工具 | 用途 |
|------|------|------|
| Logs | structlog | 故障排查 |
| Metrics | prometheus_client | 性能监控 |
| Traces | opentelemetry | 请求路径追踪 |

### Log levels

- `DEBUG` — dev 调试，生产默认关闭
- `INFO` — 正常操作（tool 调用、server 启动）
- `WARNING` — 可恢复异常（重试成功）
- `ERROR` — 操作失败但 server 存活
- `CRITICAL` — server 即将/已经崩溃

### 日志事件 schema

**固定事件类型**，不能乱加：

```python
class LogEvent(TypedDict):
    timestamp: str         # ISO 8601 UTC
    level: str             # INFO/WARN/...
    event: str             # "tool.call" / "server.init" / ...
    logger_name: str

class ToolCallStart(LogEvent):
    event: Literal["tool.call.start"]
    tool_name: str
    engagement_id: str | None
    argument_keys: list[str]   # 不含值
    dangerous: bool

class ToolCallEnd(LogEvent):
    event: Literal["tool.call.end"]
    tool_name: str
    duration_ms: int
    exit_code: int
    truncated: bool
    findings: int  # 如果 tool 返回 Findings
```

所有 log call 走 `emit(ToolCallEnd(...))`，而非自由 `logger.info("...", **kwargs)`。

### Metrics 规范

命名: `kestrel_<subsystem>_<metric>_<unit>`。

示例:
- `kestrel_tool_calls_total{tool="nuclei", status="ok"}` counter
- `kestrel_tool_duration_seconds{tool="nuclei"}` histogram
- `kestrel_scope_guard_denials_total` counter
- `kestrel_active_engagements` gauge

### Trace 规范

Span 名: `kestrel.<subsystem>.<operation>`

Attributes 必有:
- `kestrel.engagement_id`
- `kestrel.tool_name`
- `kestrel.actor`（LLM identity）

---

## 11. 测试规范

### 测试金字塔目标

```
     /\       e2e       ~20 tests (< 5 min)
    /  \      integration  ~100 tests (< 2 min)
   /____\     contract    1 per tool (< 30s)
  /______\    unit        500+ (< 30s total)
```

### 单元测试

- **Mock 所有 IO**（subprocess / 文件 / 网络）
- 每个 public 函数至少一个 happy path + 一个 error path + 一个 edge case
- 覆盖率 ≥ 80%（按行），关键模块（`security.py`, `executor.py`）100%

### Integration

- 用 **testcontainers** 跑真 docker image
- 网络调用用 **respx** 或 **pytest-httpserver** 而非 mock
- OS 差异靠 `@pytest.mark.skipif(sys.platform == ...)`

### Contract 测试

用 **schemathesis** 自动生成请求验证 JSON Schema。

```python
@schema.parametrize()
def test_shodan_search_contract(case):
    case.call()
    case.validate_response()
```

### Property-based 测试

关键逻辑用 **hypothesis**：

```python
from hypothesis import given, strategies as st

@given(
    entries=st.lists(st.text(), max_size=20),
    target=st.text(),
)
def test_scope_guard_never_crashes(entries, target):
    guard = ScopeGuard(entries)
    try:
        guard.ensure(target, tool_name="fuzz")
    except (AuthorizationError, ValueError):
        pass  # 预期异常
```

### Fuzz 测试

用 **atheris** 针对 input schema 做长时间 fuzz，放在 nightly CI。

### 禁止

- ❌ 在测试里调真 Shodan / 真扫描
- ❌ 测试之间共享状态（每个测试独立 tmp_path）
- ❌ sleep（用 event / condition 等同步）
- ❌ 随机数据没 seed

---

## 12. 依赖管理

### 工具

**uv**（替代 pip / poetry / pdm）。理由：Rust 实现，快 10-100 倍，标准化。

### 锁定

`uv.lock` 必须 commit。CI 验证：

```bash
uv lock --check
uv sync --frozen
```

### 新增依赖的审查

PR 引入新 dependency 时 reviewer 必须检查：

1. **License 兼容性**（见 G-S10）
2. **Maintenance status**（GitHub 近 6 个月有 commit 吗）
3. **Security**（OSV / Snyk 有无已知漏洞）
4. **Size**（不因小功能引入 100MB 依赖）
5. **Scope creep**（真的必要吗，能否 stdlib 代替）

### Pinning 策略

- **生产依赖**: 精确到 minor（`^1.2`）—— 允许 1.2.X patch 自动跟
- **开发依赖**: 精确到 patch
- **transitive**: 由 `uv.lock` 固定

### 定期更新

- **dependabot** 每周跑
- **Security updates**: 48h 内 review
- **Minor updates**: 双周 batch

---

## 13. 架构决策记录（ADR）

每个重要架构决策写一个 ADR。存 `docs/adr/`。

**模板** (`docs/adr/template.md`):

```markdown
# ADR-NNNN: 决策标题

- Status: proposed | accepted | deprecated | superseded by ADR-NNNN
- Date: YYYY-MM-DD
- Deciders: @alice @bob
- Technical Story: #123

## Context and Problem Statement
<!-- 2-4 段描述问题 -->

## Decision Drivers
- driver 1
- driver 2

## Considered Options
1. Option A
2. Option B
3. Option C

## Decision Outcome
Chosen option: **Option X**, because [rationale]

### Positive Consequences
- ...

### Negative Consequences / Trade-offs
- ...

## Pros and Cons of the Options

### Option A
- Good: ...
- Bad: ...

## Links
- [Relevant spec / paper / blog]
```

### 已知需要 ADR 的决策

1. ADR-0001 选择 uv 作为包管理器
2. ADR-0002 Apache 2.0 + Responsible Use 许可证组合
3. ADR-0003 MCP stdio 传输 + 未来 SSE
4. ADR-0004 Engagement 持久化用 SQLite + SQLAlchemy
5. ADR-0005 Plugin 进程内 vs 子进程隔离
6. ADR-0006 Secrets 存储策略
7. ADR-0007 Cross-platform subprocess 抽象

---

## 14. Release 流程

### Current CI baseline

- RFC-002 is the current baseline: `.github/workflows/ci.yml` must stay green
  on `ruff check`, `ruff format --check`, `mypy --strict` for
  `src/redteam_mcp/core` + `src/redteam_mcp/domain`, plus `pytest` and
  `scripts/full_verify.py` across Ubuntu/macOS/Windows on Python
  3.10/3.11/3.12.
- Weekly security automation lives in `.github/workflows/codeql.yml` and
  dependency refreshes live in `.github/dependabot.yml`.

### 版本号

**SemVer 2.0**。没有例外。

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

- MAJOR: 破坏 public API
- MINOR: 向后兼容的新功能
- PATCH: 向后兼容的 bug 修复
- PRERELEASE: `alpha.1`, `beta.2`, `rc.3`
- BUILD: `+20260420`

### 变更类别

- Breaking change → MAJOR
- New public API → MINOR
- Bug fix / refactor → PATCH
- 新 tool wrapper → MINOR
- 新 experimental API → MINOR，加 `@experimental` 装饰器

### Release 步骤

1. **Freeze**
   - 创建 `release/vX.Y.Z` 分支
   - 只接受 `fix` commits
2. **预发布**
   - Tag `vX.Y.Z-rc.1`
   - 发布到 TestPyPI
   - 至少 1 周 beta 测试
3. **最终**
   - CHANGELOG 填充
   - Tag `vX.Y.Z`
   - 自动化 workflow 发布到:
     - PyPI (`uv publish`)
     - Docker Hub / GHCR
     - GitHub Release（含 changelog）
   - 签名（cosign）
   - 生成并上传 SBOM
4. **Post-release**
   - Merge `release/vX.Y.Z` 回 `main`（若有 fix）
   - 删除 release branch
   - 宣布（可选）

### Hotfix

P0 bug 出现时：
1. 从 tag `vX.Y.Z` 切 `hotfix/xxx`
2. 修复 + 测试
3. 直接发 `vX.Y.Z+1`
4. Cherry-pick 回 `main`

---

## 15. 安全开发流程

参照 **NIST SSDF** (SP 800-218) 和 **OWASP SAMM**。

### 强制动作

**每个 PR**:
- ✅ Bandit 扫描
- ✅ Semgrep（项目自定义规则）
- ✅ Trivy（依赖漏洞）
- ✅ TruffleHog（secret 扫描）
- ✅ 如涉及 subprocess / 文件 IO / 网络 → reviewer 手动审计

**每周自动**:
- ✅ CodeQL 扫描
- ✅ SBOM 生成
- ✅ 依赖 CVE 检查
- ✅ Dependabot PR

**每个 release**:
- ✅ 完整 SAST
- ✅ 镜像漏洞扫描
- ✅ SLSA Level 2+ provenance
- ✅ cosign 签名

### Threat Modeling

每个新增 tool / 重大功能：必须补充 `THREAT_MODEL.md` 里的 STRIDE 表格。

### Vulnerability disclosure

流程在 `SECURITY.md`：
1. Reporter → `security@xxx` 或 GitHub private advisory
2. 72h 内确认
3. 90 天内修复或协调披露
4. CVE 分配（如适用）
5. Advisory 发布 + release

---

## 16. 新 Tool 贡献流程

### 步骤

1. **提 issue**（label: `tool-request`）
   - 工具名 / 上游 / license
   - 用例描述
   - 为何适合 MCP 封装

2. **Maintainer 响应（7 天内）**
   - 接受 → assign 自己或 contributor
   - 拒绝 → 给理由

3. **开发**（见 §11 测试，§8 类型）
   - 遵循 `附录 B` 模板

4. **PR**
   - PR 描述链接到 issue
   - 填完 DoD 清单

5. **Review**
   - 至少 1 个 maintainer
   - 如涉及新依赖：额外 license review

6. **Merge → CHANGELOG**

### 每个新 Tool 交付物

```
[ ] src/kestrel_mcp/tools/<cat>/<tool>_tool.py
[ ] tests/unit/tools/<cat>/test_<tool>.py       (≥3 tests, ≥80% cov)
[ ] tests/integration/tools/test_<tool>_real.py  (mock subprocess 或 testcontainer)
[ ] docs/tools/<tool>.md                        (用户文档)
[ ] examples/skills/<tool>.skill.md             (Cursor skill)
[ ] tools_manifest.yaml 更新                    (installer)
[ ] CHANGELOG.md [Unreleased] 段更新
[ ] MASTER_PLAN.md 的 tools matrix 更新
```

---

## 17. Plugin 开发契约

### 稳定 API 表面（Plugin 作者只用这些）

- `from kestrel_mcp.plugins import Plugin, tool, scope_required`
- `from kestrel_mcp.core.public import ToolResult, ScopeGuard, run_cmd`
- `from kestrel_mcp.domain import Engagement, Target, Finding`

### 禁止 import

- `kestrel_mcp.core.server` 内部
- `kestrel_mcp.tools.*` 其他工具实现
- 任何未导出到 `__init__.py` 的私有模块

CI 用 `import-linter` 强制。

### Plugin 元数据

每个 plugin 必须声明：

```python
class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    compatible_kestrel_versions = ">=1.0,<2.0"
    author = "..."
    homepage = "..."
    license = "Apache-2.0"
    required_capabilities = ["subprocess", "http_out"]
```

`required_capabilities` 用于未来沙箱化。

### Plugin 生命周期

```python
async def on_load(self, ctx):  ...     # server 启动时
async def on_unload(self, ctx):  ...   # server 关闭时
```

---

## 18. 调试指南

### 本地启动

```bash
# 启 server 在 stdio
kestrel-mcp serve --log-level DEBUG

# 直接测 tool（不走 MCP）
python -m kestrel_mcp.cli.debug call --tool shodan_count --args '{"query":"test"}'

# Replay 一条 MCP 请求
kestrel-mcp replay tests/fixtures/mcp/shodan_search_req.json
```

### 常见问题

| 症状 | 排查 |
|------|-----|
| Tool 报 ToolNotFound | `kestrel-mcp doctor` 看 binary 解析 |
| Scope guard 拒绝 | `REDTEAM_MCP_SECURITY__AUTHORIZED_SCOPE` 检查 |
| MCP 连接不上 | 在 MCP host 开 trace log; stdio 严禁 print 到 stdout |
| Subprocess 悬挂 | `execution.timeout_sec` 调小；看 log 的 duration |
| 测试挂但本地过 | CI matrix 某 OS/Python 版本差异 |

### 生产调试

- 启用 `--metrics-port 9090` 看 QPS、延迟
- 启用 OpenTelemetry 导到 Jaeger
- audit log 默认 JSONL → 用 `jq` 过滤

---

## 19. 性能规范

### 承诺（SLO）

- Tool schema 列表（list_tools）: p99 < 50ms
- 简单 tool 调用（无 subprocess）: p99 < 100ms
- Subprocess tool 调用（不含 tool 本身耗时）: p99 < 200ms
- Cold start: < 1s
- 内存: 基线 < 150MB

**超过 SLO 需要 ADR 记录原因。**

### 性能 CI

`benchmarks/` 中的测试每个 release 跑一次。结果 commit 到 `docs/perf/history.md`。
对比上版退化 > 10% → release 阻塞。

---

## 20. 文档规范

### 分层

| 类型 | 目录 | 受众 | 维护者 |
|------|------|------|--------|
| API reference | 自动生成 from docstring | plugin 作者 | 代码作者 |
| User guide | `docs/user/` | 终端用户 | 功能作者 |
| Architecture | `docs/architecture/` | maintainer | maintainer |
| ADR | `docs/adr/` | maintainer | 决策者 |
| Tutorial | `docs/tutorials/` | 新用户 | 任意 |

### 每个新功能 PR 必须同时更新

- [ ] 对应的 user guide
- [ ] 如果改 API → API reference 自动生成无需手动
- [ ] 如果改交互 → tutorial 快速截图更新（如有）

### 文档 CI

- **mkdocs build --strict** 必须绿
- **vale**（散文 linter）可选，检查术语一致性
- 链接检查 `lychee`

### 术语表

`docs/glossary.md` 统一术语：
- Engagement, Target, Finding, Credential, Artifact, Scope, Actor
- 不要混用 "target" 和 "host"

---

# 附录 A — PR 模板（完整）

见 §5。

# 附录 B — 新 Tool 模板（代码）

见 `MASTER_PLAN.md` 附录 B。

# 附录 C — CI 配置

见 `MASTER_PLAN.md` 附录 C。

# 附录 D — CODEOWNERS 示例

```
# .github/CODEOWNERS
* @maintainer1 @maintainer2

/src/kestrel_mcp/core/   @alice
/src/kestrel_mcp/tools/  @bob @alice
/docs/                   @docteam
/.github/                @alice
/SECURITY.md             @security-team
```

---

# 相关文档

- [MASTER_PLAN.md](./MASTER_PLAN.md) — 战略路线图
- [GAP_ANALYSIS.md](./GAP_ANALYSIS.md) — 工程缺陷清单
- [DOMAIN_MODEL.md](./DOMAIN_MODEL.md) — 业务实体定义（待建）
- [THREAT_MODEL.md](./THREAT_MODEL.md) — 安全威胁分析（待建）
- [ARCHITECTURE.md](./ARCHITECTURE.md) — 架构决策摘要（待建）
