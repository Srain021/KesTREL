# Product Lines Strategy: Pro vs Team Edition

> 本文档定义 **商用 Pro 版** 和 **队伍私用 Team Edition** 的分叉策略。
> 写法原则：
> - 每个重大决策给 **3-4 个候选方案** 并列对比
> - 有明确 **推荐**，说明理由
> - 末尾给 **你需要拍板的 5 个决策点**
>
> 参考：AUDIT.md · AUDIT_V2.md · CTF_ECOSYSTEM_RESEARCH.md

**Date**: 2026-04-21
**Status**: PROPOSAL — 等待拍板

---

## Part 1 — 两版产品定位

### Pro Edition (商用)

- **目标客户**: 安全咨询公司、红队服务提供商、SOC 团队
- **核心卖点**:
  - 合规（OWASP ASVS + NIST SSDF + SLSA）
  - 审计链（不可篡改 evidence）
  - 多客户隔离（每 engagement 独立 tenant）
  - 威胁建模内置
  - API/CLI 稳定性（SemVer + LTS）
  - 可商用报告模板
- **非目标**: 比赛极致性能
- **优先级矩阵**: 稳定 > 合规 > 易用 > 性能

### Team Edition (队伍私用 / CTF)

- **目标用户**: 4 人 CTF 战队、CTF 竞赛组、学校红队
- **核心卖点**:
  - 比赛速度（flag auto-submit、bootstrap 自动化）
  - 团队协作（shared engagement、realtime sync、共享凭证）
  - 知识沉淀（pattern cards、cross-engagement RAG）
  - 成本控制（多模型路由）
  - **无限制模式**（比赛需要最大权限，不做 scope 强制）
- **非目标**: 对外客户合规
- **优先级矩阵**: 性能 > 协作 > 知识 > 稳定

---

## Part 2 — 分叉策略选型（4 个候选方案）

### 候选 A: 双仓分叉 (Two Repos)

```
github.com/yourorg/kestrel-pro      (main, public)
github.com/yourorg/kestrel-team     (private, 队内 fork)
```

- **优点**
  - 彻底隔离，team 可以丢弃合规约束、放肆改
  - team 可以关闭 scope guard、关闭 rate limit
  - 无污染 Pro 代码库
- **缺点**
  - 重复维护极度痛苦
  - 核心 bug 要 cherry-pick 两次
  - 测试覆盖要重建
  - 3-4 个月后必然分歧过大

**适合场景**: 两版产品语义差异巨大（>40%）

---

### 候选 B: Monorepo + 特性标志 (Feature Flags in One Repo) ⭐ **推荐**

```
kestrel-mcp/
├── src/kestrel_mcp/
│   ├── core/                 # Pro + Team 共享
│   ├── domain/               # Pro + Team 共享
│   ├── tools/                # Pro + Team 共享
│   ├── pro/                  # Pro 专属：billing, multi-tenant, compliance
│   ├── team/                 # Team 专属：CTF domain, realtime sync, vaultwarden
│   └── editions/
│       ├── pro.py            # 构建 Pro 版 Settings + 默认值
│       └── team.py           # 构建 Team 版 Settings + 默认值
├── config/
│   ├── defaults.pro.yaml
│   └── defaults.team.yaml
```

- **启动方式**
  - `kestrel --edition=pro server` (默认)
  - `kestrel --edition=team server`
  - 或环境变量 `KESTREL_EDITION=team`
- **特性切换机制**
  ```python
  # settings.py
  class Settings(BaseSettings):
      edition: Literal["pro", "team"] = "pro"
      features: FeatureFlags = Field(default_factory=FeatureFlags)

  class FeatureFlags(BaseModel):
      # 每个 V-/T- 特性一个 flag
      vaultwarden_sync: bool = False
      realtime_sync: bool = False
      challenge_flag_domain: bool = False
      flag_auto_submit: bool = False
      # ...
  ```
- **Edition preset 机制**
  ```python
  # editions/team.py
  TEAM_DEFAULTS = FeatureFlags(
      vaultwarden_sync=True,
      realtime_sync=True,
      challenge_flag_domain=True,
      flag_auto_submit=True,
      scope_enforcement="warn_only",  # Team 版 scope 不 block
      rate_limit_enabled=False,        # Team 版不限速
      cost_ledger=True,
      pattern_cards=True,
      # ...
  )
  ```
- **RFC 编写时的规则**
  - 每个 RFC 明确标 `edition: pro | team | both`
  - RFC 实现时加 `if settings.features.xxx:` gate
- **优点**
  - 只有一个代码库
  - 核心 bug 修一次两边都修
  - 测试矩阵：pro + team 两种配置各跑一遍 CI
  - 开源时只 ship Pro 版（team 模块受控可选）
- **缺点**
  - feature flag 数量多 → 配置复杂
  - 需要严格的 flag 清理纪律（老 flag 不清理会成"特性墓地"）
  - 某些深层差异（比如 domain model 的 Challenge/Flag）硬塞到 flag 里会变屎山

**推荐理由**:
- v2 里 28 个新 gap 大部分是**增量**，不是**替代**，天然适合 feature flag
- CI 可以跑 `--edition=pro` 和 `--edition=team` 两遍 regression
- Team 版特殊代码用子包隔离（`src/kestrel_mcp/team/`），清晰边界
- 遇到真正不可调和的 domain 差异（如 V-D1 Challenge/Flag）时再升级到方案 C

---

### 候选 C: Monorepo + Package 拆分 (Multi-Package)

```
kestrel-mcp/                  # Monorepo
├── packages/
│   ├── core/                 # 共享：domain, executor, scope
│   ├── pro/                  # PyPI: kestrel-pro
│   │   └── pyproject.toml    # depends on: core
│   ├── team/                 # PyPI: kestrel-team
│   │   └── pyproject.toml    # depends on: core
│   └── meta-pro/             # PyPI: kestrel (默认安装=pro)
│       └── pyproject.toml    # extras: [team]
```

- **用户体验**
  - `pip install kestrel` → Pro 版
  - `pip install kestrel[team]` → 加装 Team 模块
- **优点**
  - 物理隔离，package 层面清晰
  - Team 特性可以独立 release
  - 适合开源商用双轨
- **缺点**
  - uv workspace 配置复杂
  - tests/ 目录如何分配？（需要决策）
  - 版本号独立，发版协调复杂

**适合场景**: 产品成熟后（Pro v2+）再考虑演进到这个方案

---

### 候选 D: Profile 模式 (Single Binary, 运行时切换)

```bash
# 启动时按 profile 加载
kestrel server --profile=pro
kestrel server --profile=team
kestrel server --profile=custom --config=my.yaml
```

- 本质是候选 B 的**轻量版**：不分子包，只用配置 profile
- **优点**: 实现最简单
- **缺点**:
  - Team 专属代码会污染 Pro 发行包
  - 开源时 "合规" 和 "无限制" 都在一个 binary 里，法律风险大
  - pip install 后 ship 的 wheel 里有所有代码

**不推荐**：法律风险（Pro 版卖给企业时，里面藏一个 "无限制模式" 开关对合规审查很难看）

---

### 对比矩阵

| 维度 | A 双仓 | **B Feature Flags** | C 多包 | D Profile |
|------|--------|---------------------|--------|-----------|
| 实现难度 | 高 | 中 | 高 | 低 |
| 维护成本 | 极高 | 中 | 中 | 低 |
| Pro / Team 隔离度 | 完全 | 强 | 强 | 弱 |
| 开源合规友好 | 最高 | 高 | 高 | **低** |
| CI 配置复杂度 | 2 倍 | 1.5 倍 | 2 倍 | 1 倍 |
| 核心 bug 修复成本 | 2 倍 | 1 倍 | 1 倍 | 1 倍 |
| 后期演进空间 | 差 | 好 | 最好 | 差 |
| 适配 28 个 gap | 过度 | 刚好 | 过度 | 不足 |

**最终推荐**: **候选 B** — Monorepo + Feature Flags + 子包隔离

**演进路径**: B → 2027 年后若 Team 版用户 >100 且维护分叉明显，升级到 C

---

## Part 3 — 特性矩阵

28 个 AUDIT_V2 gap + 原有 13 个 gap，按 edition 分配：

### 核心平台（Pro + Team 共享）

所有 AUDIT v1 的 D-1..D-13 → **都属共享核心**

| Feature | 所属 RFC | 是否 gate | 说明 |
|---------|---------|----------|------|
| 包名统一 kestrel-mcp | RFC-H01 | ❌ 共享 | |
| uv lock | RFC-001 | ❌ 共享 | |
| CI/CD | RFC-002 | ❌ 共享 | |
| Credential seal | RFC-003 | ❌ 共享 | |
| Plugin namespace | RFC-V03 | ❌ 共享 | |
| Rich description | RFC-B02 | ❌ 共享 | |
| Attack graph replay | RFC-V02 | ⚠️ flag | Pro 默认 off，Team on |
| Cost ledger | RFC-V07 | ⚠️ flag | Pro 默认 on，Team on |
| Benchmark harness | RFC-V09 | ❌ 共享 | Dev-only |
| Tool complexity tier | RFC-V05 | ⚠️ flag | 默认 off |
| Tool soft timeout | RFC-V06 | ❌ 共享 | |
| Untrust wrapping | RFC-V08 | ❌ 共享 | |
| License compat matrix | RFC-V10 | ❌ 共享 | 文档性 |
| Browser automation | RFC-V12 | ⚠️ flag | 默认 off |
| Subtask guidance | RFC-V04 | ❌ 共享 | |
| Model routing | RFC-V01 | ⚠️ flag | 默认 off |

### Pro 专属

| Feature | 备注 |
|---------|------|
| Multi-tenant engagement 隔离 | Pro v2 |
| 客户报告白标 | Pro v2 |
| SLSA level 3 供应链 | Pro v2 |
| STRIDE 威胁模型跟踪 | RFC-B03 |
| OWASP ASVS 合规 checklist | Pro v2 |
| 发票/billing 集成 | Pro v2（暂不做）|

### Team Edition 专属

| Feature | RFC | 备注 |
|---------|-----|------|
| CTF Challenge/Flag domain | RFC-T06 | 核心 |
| Flag auto-submission | RFC-T07 | 核心 |
| Realtime engagement sync (PostgreSQL) | RFC-T04 | 核心 |
| Vaultwarden 集成 | RFC-T02 | |
| Obsidian Team Vault 模板 | RFC-T01 | |
| tmate 共享 shell | RFC-T03 | |
| Contribution / scoreboard | RFC-T05 | |
| Pre-match bootstrap 命令 | RFC-T08 | |
| 2-hour rule 止损 | RFC-T09 | |
| Pattern card library | RFC-T10 | |
| Cross-engagement RAG | RFC-T11 | |
| Public writeup export | RFC-T12 | |
| **Scope enforcement=warn_only** | config | 无限制模式 |
| **Rate limit disabled 默认** | config | 比赛不限速 |
| **Credential encryption 可选** | config | 队内共享优先 |

---

## Part 4 — 版本号策略

### 候选 1: 分别独立版本号

- `kestrel-pro v1.0.0`
- `kestrel-team v0.3.0`

**问题**: 用户混淆 "我用的是哪一版"

### 候选 2: 同步版本号 + edition 标签 ⭐ **推荐**

- `kestrel v0.2.0 (pro-edition)`
- `kestrel v0.2.0 (team-edition)`
- 同一个 git tag，同一个 CHANGELOG，不同 binary 打包

**推荐理由**:
- 清晰知道 core 能力一致
- Team 特性只在 team binary 中 active
- 遵循 monorepo 哲学

### SemVer 约定

- **MAJOR**: Pro 或 Team 的公共 API 不兼容变化
- **MINOR**: 新增 feature（flag 默认 off，不破坏现有行为）
- **PATCH**: Bug fix，无 feature 变化

### LTS 策略（Pro 版）

- Pro 版每年 Q1 发 LTS，支持 18 个月
- Team 版 rolling release，无 LTS 概念（赛季性替换更快）

---

## Part 5 — 开源策略

### 候选 1: 全开源 (MIT)

- **优点**: 社区吸引力最大
- **缺点**: Pro 版商用时客户可能说 "我自己就装开源版了"

### 候选 2: 核心开源 + 商业功能闭源 ⭐ **推荐**

- **开源部分** (MIT + Responsible Use Addendum):
  - `src/kestrel_mcp/core/`
  - `src/kestrel_mcp/domain/` (除 Challenge/Flag)
  - `src/kestrel_mcp/tools/` (所有 tool module，除 team 专属工具)
  - `src/kestrel_mcp/webui/` 基础
  - RFC 体系、skills
- **私有部分**（Pro 商业）:
  - Multi-tenant
  - 白标报告
  - 合规 dashboard
  - Enterprise SSO
- **Team 版**: **保持私有直到比赛结束后考虑开源**
  - 理由：比赛中 Team Edition = 队伍核心优势，开源就是送给对手
  - 比赛结束后可以开源（或把某些能力合并入 Pro 社区版）

### 候选 3: 双 license (AGPL + 商业 license)

- 社区版 AGPL（开源但强传染）
- 企业版购买商业 license 解除
- **风险**: AGPL 对 Pro 企业客户不友好

**最终推荐**: 候选 2 — 核心 MIT 开源 + Pro 商业功能 + Team **先闭源后视情况**

---

## Part 6 — 代码组织示意（按推荐方案 B）

```
kestrel-mcp/
├── src/kestrel_mcp/
│   ├── __init__.py
│   ├── core/                          # 共享
│   │   ├── context.py
│   │   ├── services.py
│   │   ├── paths.py
│   │   ├── redact.py
│   │   ├── rate_limit.py
│   │   └── cost_ledger.py             [NEW: RFC-V07]
│   ├── domain/                        # 共享（除 CTF 专属）
│   │   ├── entities.py
│   │   ├── services/
│   │   │   ├── engagement_service.py
│   │   │   ├── scope_service.py
│   │   │   ├── target_service.py
│   │   │   ├── finding_service.py
│   │   │   └── credential_service.py
│   │   └── storage.py
│   ├── tools/                         # 共享工具模块
│   │   ├── nuclei_tool.py
│   │   ├── sliver_tool.py
│   │   └── ...
│   ├── pro/                           [NEW] Pro 专属
│   │   ├── __init__.py
│   │   ├── tenant.py
│   │   ├── compliance.py
│   │   └── billing/
│   ├── team/                          [NEW] Team 专属
│   │   ├── __init__.py
│   │   ├── ctf/                       # RFC-T06/T07 Challenge/Flag
│   │   │   ├── entities.py            # Challenge, Flag
│   │   │   ├── services.py
│   │   │   └── submission_adapters/
│   │   │       ├── htb.py
│   │   │       ├── pico.py
│   │   │       └── generic.py
│   │   ├── vaultwarden.py             # RFC-T02
│   │   ├── tmate.py                   # RFC-T03
│   │   ├── pattern_cards.py           # RFC-T10
│   │   ├── rag.py                     # RFC-T11
│   │   ├── realtime_sync.py           # RFC-T04
│   │   ├── tools/                     # Team 专属 MCP tools
│   │   │   ├── flag_tool.py
│   │   │   ├── challenge_tool.py
│   │   │   └── pattern_tool.py
│   │   └── templates/
│   │       └── obsidian_vault/        # RFC-T01
│   ├── editions/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── pro.py                     # PRO_DEFAULTS
│   │   └── team.py                    # TEAM_DEFAULTS
│   ├── features.py                    [NEW] FeatureFlags Pydantic
│   ├── config.py                      [扩展] 加 edition + features
│   ├── server.py                      [扩展] 按 features 注册 tools
│   ├── webui/
│   └── ...
├── config/
│   ├── defaults.pro.yaml
│   └── defaults.team.yaml
├── tests/
│   ├── unit/
│   ├── pro/                           # Pro 专属测试
│   └── team/                          # Team 专属测试
└── pyproject.toml                     # extras: [team]
```

---

## Part 7 — 需要你拍板的 5 个决策点

请针对每个决策点选择或给反馈，这决定我们接下来 RFC 的写法和 roadmap。

### 决策 1: 分叉策略

- [ ] A 双仓
- [x] **B Feature Flags（推荐）**
- [ ] C 多包
- [ ] D Profile

### 决策 2: 版本号策略

- [ ] 1 独立版本号
- [x] **2 同步版本号 + edition 标签（推荐）**

### 决策 3: 开源策略

- [ ] 1 全开源
- [x] **2 核心 MIT + Pro 商业 + Team 先闭源（推荐）**
- [ ] 3 AGPL 双 license

### 决策 4: Team Edition 的"无限制模式"默认值

- [ ] A `scope_enforcement=strict` 默认，手工解除（安全优先）
- [ ] B `scope_enforcement=warn_only` 默认（自由优先）
- [x] **C `scope_enforcement=strict` 默认，但 Team 版提供一键 `kestrel team --unleash` 解除（推荐：安全可撤销）**

### 决策 5: Team Edition 的 MVP 范围

4 个 Team 极高优先级 gap 里要不要**全做**：
- V-C2 Attack graph replay (5 SP)
- V-T4 Realtime sync (5 SP)
- V-D1 Challenge/Flag domain (5 SP)
- V-D2 Flag submission (3 SP)

共 **18 SP ≈ 3-4 周 pair**。

- [ ] A 全做（Team MVP 范围 = 4 个）
- [x] **B 先做 D1 + D2（核心 domain+submission），其他延后（推荐，保证最小可用）**
- [ ] C 先做 D1 + D2 + T4（加实时同步），replay 延后
- [ ] D 其他组合（请说明）

---

## Part 8 — 一旦你拍板后，我的下一步

假设你选默认推荐（B / 2 / 2 / C / B），我接下来：

### 第 1 批 RFC（共享核心，属 Pro + Team）
- RFC-V01 Model routing
- RFC-V03 Tool namespace
- RFC-V04 Subtask guidance
- RFC-V05 Tool complexity tier
- RFC-V06 Tool soft timeout
- RFC-V07 Cost ledger
- RFC-V08 Untrust wrapping
- RFC-V09 Benchmark harness
- RFC-V10 License matrix
- RFC-V11 Plugin registry MVP
- RFC-V12 Browser automation
- RFC-V02 Attack graph replay
- RFC-A04 Edition + FeatureFlags infra（**最优先，前置条件**）

### 第 2 批 RFC（Team 专属）
- RFC-T06 CTF Domain (Challenge/Flag)  ← Team MVP 起点
- RFC-T07 Flag submission  ← Team MVP
- RFC-T04 Realtime sync（可选，按决策 5）
- RFC-V02 Attack graph replay（可选，按决策 5）
- RFC-T02 / T03 / T05 / T08 / T09 / T10 / T11 / T12 / T01（按优先级排期）

### 写法
- 每个 RFC 遵循 RFC-000-TEMPLATE.md
- 标 `edition: pro | team | both`
- 标 `feature_flag: xxx`（如适用）
- 包含 `verify_cmd` 和 `rollback_cmd`
- 大小严格符合 AGENT_EXECUTION_PROTOCOL 的 budget 约束

---

---

## Part 9 — 拍板结果（2026-04-21）

| # | 决策 | 选定 | 备注 |
|---|------|------|------|
| 1 | 分叉策略 | **B Feature Flags + 子包隔离** | |
| 2 | 版本号 | **2 同步版本号 + edition 标签** | 后续执行 |
| 3 | 开源策略 | **2 核心 MIT + Team 先闭源** | 后续执行 |
| 4 | Team 无限制模式 | **B `scope_enforcement=warn_only` 默认** | **用户明确：就是要无限制** |
| 5 | Team MVP 范围 | **砍 V-D1..D5 全套 CTF domain**；直接用现有 Engagement/Target/Finding | **用户明确：不做 Challenge/Flag 新概念，最快能用** |

### Team Edition 本质重定义

原定位：CTF 专属战队工具（4 人 CTF 战队 + Flag 管理 + 赛事集成）
**新定位**：**内部队伍的"无限制红队版"** —— 不搞新 domain，只把现有框架的所有限制关掉 + 加团队协作

### Team MVP 新范围（砍刀后）

**做（MVP 三件套）**：
1. **Edition & FeatureFlags 基建** (新 RFC-A04) — Pro/Team 都必须，前置
2. **Team "Unleashed" 预设** (新 RFC-T00) — 关 scope 强制、关 rate limit、放宽 credential、加 `--unleash` 默认
3. **Team Bootstrap 命令** (新 RFC-T08) — 一键起服务 + 创默认 engagement + 预载常用工具目标

**延后（按需再做，非 MVP 阻塞）**：
- V-T2 Vaultwarden 集成
- V-T4 Realtime sync（PostgreSQL 后端）
- V-C2 Attack graph replay
- V-K1/K2 Pattern cards + RAG
- V-E4 Browser automation

**彻底删除（Team 版不做）**：
- V-D1..D5 全部 — CTF Challenge/Flag domain、Flag submission、2h rule、pre-match bootstrap 里的 CTF-specific 部分

### 共享核心仍按 V- 系列做

AUDIT_V2 的 V- 系列（V01..V12）**大部分仍保留**，但降级为"等 Team MVP 能跑起来后再排期"，不堵 MVP。

---

## Changelog

- **2026-04-21 初版** — 基于 AUDIT_V2 的 28 个 gap 设计 Pro / Team 分叉策略；4 方案对比；5 个拍板点
- **2026-04-21 v1.1** — 用户拍板：方案 B + 无限制模式 + 砍 CTF domain；Team MVP 缩减为 3 个 RFC（A04 + T00 + T08）
