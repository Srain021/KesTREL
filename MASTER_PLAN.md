# 🗺️ MASTER PLAN — 从地基到开源发布的全项目蓝图

> **这份文档是项目宪法**。所有后续决策必须回到这里对照。
> 不明确的地方先补这里，再写代码。

**Version**: 1.0-draft
**Date**: 2026-04-20
**Owner**: bofud + Claude (pair programming)

---

## 📋 目录

- [Part 0 — 总览与现状](#part-0--总览与现状)
- [Part 1 — 项目定位与目标](#part-1--项目定位与目标)
- [Part 2 — 时间表（重新评估）](#part-2--时间表重新评估)
- [Part 3 — 地基（Phase 0）](#part-3--地基phase-0)
- [Part 4 — 跨平台支持矩阵](#part-4--跨平台支持矩阵)
- [Part 5 — 工具生态扩展（Phase 1）](#part-5--工具生态扩展phase-1)
- [Part 6 — Plugin 系统（Phase 2）](#part-6--plugin-系统phase-2)
- [Part 7 — Skills 与 MCP Tools 的关系](#part-7--skills-与-mcp-tools-的关系)
- [Part 8 — 测试、质量、安全审计（Phase 3）](#part-8--测试质量安全审计phase-3)
- [Part 9 — 文档与发布（Phase 4）](#part-9--文档与发布phase-4)
- [Part 10 — 社区与推广（Phase 5）](#part-10--社区与推广phase-5)
- [Part 11 — 商业化路径（可选）](#part-11--商业化路径可选)
- [Part 12 — 风险清单](#part-12--风险清单)
- [附录 A — 50+ 工具矩阵](#附录-a--50-工具矩阵)
- [附录 B — Tool/Skill/Plugin 模板](#附录-b--toolskillplugin-模板)
- [附录 C — CI/CD 配置模板](#附录-c--cicd-配置模板)

---

# Part 0 — 总览与现状

## 当前真实状态（2026-04-20）

### ✅ 已完成
```
代码量       31 个 Python 文件，~200 KB
测试          27 passed / 1 skipped / 8/8 e2e
MCP tools     35 个（6 模块 + 2 workflow）
CLI           version / doctor / list-tools / serve 可用
Cursor 集成   已注册，配置就绪
ScopeGuard    空-scope deny + wildcard + CIDR
审计日志      结构化 JSON 输出
依赖          venv 里 ~60 个包，Tier1+2+3 全装
Shodan        API Key 已配，oss 计划可用
所有二进制    nuclei/sliver/caido-cli/ligolo/evilginx 全就绪
Defender      hacking-tools/ 已排除
```

### ❌ 未完成（从产品化角度）
```
许可证         MIT → 需升级 Apache 2.0 + Responsible Use Addendum
品牌           名字 "redteam-mcp" 太 generic
跨平台         当前只在 Windows 验证
CI/CD          无（手动测试）
PyPI/Docker    未发布
文档站点       无（只有 README）
Plugin 系统    无（所有 tool 硬编码）
工具数         只有 6 个模块（行业基线是 50+）
社区           无
Havoc          因 CGO 依赖未编译
```

### 已投入时间与产出
| 阶段 | 耗时 | 产出 |
|------|------|------|
| 设计与架构 | ~2h | README + LICENSE + 架构文档 |
| 核心代码 | ~3h | server + config + security + executor |
| 7 个 tool 模块 | ~4h | 35 个 MCP tool |
| 测试 | ~1h | 28 个测试用例 |
| 安装与验证 | ~2h | venv / CLI / e2e |
| 配置与部署 | ~1h | Cursor 集成 / scope 配置 |
| **合计** | **~13 小时** | **能跑的 MVP** |

---

# Part 1 — 项目定位与目标

## 一句话

> **面向红队 / 渗透测试工程师的 MCP 服务器，让任意 LLM (Cursor / Claude / GPT / Cline) 通过自然语言调度 50+ 进攻性安全工具，内置 scope 守卫、审计日志、跨平台支持。**

## 与竞品的差异

| 项目 | 覆盖工具数 | LLM 原生 | 开源 | 跨平台 | 主线焦点 |
|------|-----------|---------|------|-------|---------|
| **Metasploit** | 1000+ | ❌ | ✅ GPL | ✅ | 漏洞利用 |
| **Caldera (MITRE)** | ~200 | ⚠️ plugin | ✅ Apache | ✅ | 自动化 TTP |
| **PentestGPT** | 几个 | ✅ CLI | ✅ MIT | ⚠️ | LLM 咨询 |
| **HackBot / HackerGPT** | 闭源 | ✅ | ❌ | ⚠️ | SaaS |
| **本项目** | 50+ | ✅ **MCP 原生** | ✅ | ✅ | **LLM 调度层** |

## 三条护城河

1. **MCP 原生设计** — 别人是事后加 LLM 适配，我们从第一天就是 MCP
2. **内置合规** — ScopeGuard + 审计 + dry-run 在 core，不是可选
3. **Plugin 生态** — 任何 tool wrapper 30 行代码就能贡献（见附录 B）

## 目标用户画像

```
主要:
  - 渗透测试工程师（Pentester）
  - 红队成员（Red Team Operator）
  - Bug bounty hunter
  - CTF 选手
  - 安全研究员

次要:
  - 蓝队 / Blue team (评估攻击面)
  - 安全教师 / 培训机构
  - 大学安全社团
```

## 非目标用户（明确排除）

```
- 未授权攻击者（法律风险）
- 儿童 / 学生未经指导（教育路径不同）
- 普通开发者（学习曲线太陡）
```

## 成功标准（12 个月）

| 指标 | 目标 | 参考 |
|------|------|------|
| GitHub Stars | 1000+ | Sliver 用 2 年到 10k |
| PyPI 月下载 | 10k+ | nuclei-templates 约 50k |
| 贡献的 tool wrapper | 30+ | 社区 > 官方 |
| DEFCON Arsenal 被接收 | 是 | 2027 Arsenal |
| 活跃 Discord 成员 | 200+ | Sliver Discord 约 3k |

---

# Part 2 — 时间表（重新评估）

## 关键事实

我（Claude）能做的：
- **编码速度**：人类 10 倍（我直接写完整模块）
- **文档速度**：人类 8 倍（结构化输出）
- **测试速度**：人类 5 倍（但测试要手动验证，打折）
- **调试速度**：人类 2~3 倍（被网络 / 权限卡住时）
- **决策速度**：人类 0.5 倍（我需要你拍板）

我不能做：
- **物理下载大文件**（你的网络带宽是瓶颈）
- **等待第三方服务**（GitHub rate limit、OAuth）
- **法律文书签署**（CLA 需要真人签）
- **社区运营**（写 tweet、回 issue、吸引关注）

**有效加速 = 约 6-10 倍**（不是 100 倍）。

## 修正后的时间表

### 单人干（无 Claude 辅助）基线
| Phase | 任务 | 单人耗时 |
|-------|-----|---------|
| Phase 0 | 地基重构 | 2 周 |
| Phase 1 | 加 15 个 tool | 4 周 |
| Phase 2 | Plugin 系统 | 2 周 |
| Phase 3 | 测试与审计 | 2 周 |
| Phase 4 | 文档与发布 | 1 周 |
| Phase 5 | 社区建设 | 持续 |
| **合计到 v1.0** | | **~11 周 (~3 个月)** |

### 和我 pair 干
| Phase | 任务 | 合作耗时 | 你投入 |
|-------|-----|---------|-------|
| Phase 0 | 地基重构 | **2 天** | 2h/天 |
| Phase 1 | 加 15 个 tool | **5 天** | 2h/天 |
| Phase 2 | Plugin 系统 | **2 天** | 2h/天 |
| Phase 3 | 测试与审计 | **3 天** | 3h/天 |
| Phase 4 | 文档与发布 | **1 天** | 3h/天 |
| Phase 5 | 社区建设 | 持续 | 你主导 |
| **合计到 v1.0** | | **~13 天 (~2 周)** | ~35h |

**对比**: 3 个月 → 2 周 = 约 **6.5 倍加速**。

## 每日节奏建议

```
09:00-11:00  你和我 pair 编码（我写，你审，你拍板）
11:00-12:00  你测试我写的代码
14:00-16:00  你做需要真人的事（社区 / 法律 / 品牌）
16:00-17:00  我们复盘当天进度 + 规划明天
```

---

# Part 3 — 地基（Phase 0）

> **这个阶段必须做对。返工成本最高。**

## Phase 0 每一步（2 天）

### Step 0.1 — 项目改名（30 分钟）

#### 候选名字
```
1. Armory         (军械库)  — 中性，有辨识度
2. RedWing        (红翼)    — 红队 + 助手
3. Kestrel-MCP    (茶隼)    — 致敬 MITRE Kestrel，小众但高级
4. Offensive-Ctx  (进攻上下文) — 学术友好
5. HackOps        (黑客运维) — Ops 风
```

**决策矩阵**
| 名字 | 搜索结果干净度 | 国际化 | 域名可用 | 语义 |
|------|--------------|-------|---------|------|
| Armory | 🟡 有冲突 | ✅ | ⚠️ | ✅ |
| RedWing | 🟢 | ✅ | ✅ | ✅ |
| Kestrel-MCP | 🟢 | ✅ | ✅ | ⚠️ |
| Offensive-Ctx | 🟢 | ⚠️ | ✅ | ⚠️ |
| HackOps | 🟡 | ✅ | ⚠️ | ✅ |

**我的推荐**: **`kestrel-mcp`**（茶隼）— 小巧 / 精准 / 不暴力，致敬 MITRE Kestrel threat hunting。

#### 执行步骤
```
1. GitHub 创建新 repo: kestrel-mcp
2. 重命名 Python package: redteam_mcp → kestrel_mcp
3. 更新 pyproject.toml, __init__.py
4. 全局 grep 替换旧名
5. 更新所有文档（README / QUICKSTART / CTF_CHEATSHEET / 本文档）
6. 注册 PyPI 名字占位（pip install kestrel-mcp 占下）
7. 买域名：kestrel-mcp.dev 或 kestrel.sh
```

**验收标准**:
- `pytest` 全绿
- `pip install kestrel-mcp` 查询返回"package exists"
- 不存在任何遗留 "redteam-mcp" 字符串

---

### Step 0.2 — License 升级（1 小时）

#### 当前: MIT
#### 目标: **Apache 2.0 + Responsible Use Addendum**

**为什么 Apache > MIT**
- ✅ 专利保护（防止贡献者反起诉）
- ✅ 明确的 Notice + Patent grant
- ✅ 商业友好（所有大厂默认接受）
- ⚠️ 略长（30 行 vs MIT 的 7 行）

**Responsible Use Addendum** 独立文件，不修改 Apache 2.0 原文（避免变成"proprietary"）。

#### 文件结构
```
LICENSE              ← Apache 2.0 原文
NOTICE               ← 归属（Apache 要求）
RESPONSIBLE_USE.md   ← 额外声明
CODE_OF_CONDUCT.md   ← 贡献者行为准则（Contributor Covenant）
SECURITY.md          ← 漏洞报告流程
```

**验收标准**:
- 通过 OpenSSF Scorecard 的 license check
- 包含双重用途声明
- 不涉及任何会把 license 变成非 OSI 认证的限制

---

### Step 0.3 — 仓库结构终版（1 小时）

#### 目标结构
```
kestrel-mcp/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # lint + test matrix
│   │   ├── release.yml          # auto PyPI + Docker
│   │   └── codeql.yml           # security scan
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug.yml
│   │   ├── feature.yml
│   │   └── tool_request.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── index.md                 # 文档站点入口
│   ├── quickstart.md
│   ├── architecture.md
│   ├── tools/                   # 每个 tool 一页
│   ├── plugins/
│   └── contributing.md
├── examples/
│   ├── hello_world_plugin/
│   ├── cursor_config.json
│   ├── claude_desktop_config.json
│   └── cline_config.json
├── src/kestrel_mcp/
│   ├── core/                    # 框架核心（不含 tool）
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── executor.py
│   │   ├── logging.py
│   │   └── server.py
│   ├── tools/                   # 官方 tool modules
│   │   ├── base.py
│   │   ├── recon/               # 按阶段分类
│   │   │   ├── shodan_tool.py
│   │   │   ├── subfinder_tool.py
│   │   │   └── ...
│   │   ├── scan/
│   │   ├── web/
│   │   ├── exploit/
│   │   ├── c2/
│   │   ├── postex/
│   │   └── cracking/
│   ├── workflows/
│   ├── plugins/                 # plugin 加载框架
│   └── cli/
│       ├── __main__.py
│       ├── doctor.py
│       ├── install.py           # tool 自动安装
│       └── register.py          # MCP host 注册
├── plugins-official/            # 可选的一方 plugin
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── scripts/
│   ├── install/                 # 平台特定
│   │   ├── windows.ps1
│   │   ├── linux.sh
│   │   └── macos.sh
│   ├── build_release.py
│   └── tool_downloader.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── LICENSE
├── NOTICE
├── RESPONSIBLE_USE.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── MASTER_PLAN.md               ← 本文档
├── CTF_CHEATSHEET.md
└── QUICKSTART.md
```

#### 关键改动 vs 当前
- ✅ **按阶段分组 tools**（recon / web / c2 等）— 未来加 50 个 tool 时不乱
- ✅ **plugins/ 目录独立**
- ✅ **docs/ 站点**（MkDocs 或 Docusaurus）
- ✅ **examples/ 多 host 配置**（Cursor / Claude Desktop / Cline / Zed）

---

### Step 0.4 — CI/CD 基础设施（2 小时）

#### GitHub Actions 3 个 workflow

**1. `ci.yml`** — 每个 PR 触发
```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [checkout, setup-python, pip install ruff mypy, ruff check, mypy src/]

  test:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python: ["3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps: [checkout, setup-python, pip install -e .[dev], pytest tests/unit]

  integration:
    runs-on: ubuntu-latest
    services:
      # 可能用 docker 跑一些模拟环境
    steps: [pytest tests/integration]
```

**2. `release.yml`** — tag 触发
```yaml
jobs:
  pypi:
    steps: [build, twine upload --skip-existing]
  docker:
    steps: [buildx build --platform linux/amd64,linux/arm64, push to ghcr.io]
  github-release:
    steps: [create release with changelog]
```

**3. `codeql.yml`** — 每周一次安全扫描

#### 版本策略
**SemVer**（Semantic Versioning 2.0）

```
v1.0.0          第一个稳定版
v1.0.x          仅 bugfix
v1.x.0          新功能（向后兼容）
v2.0.0          breaking change
v1.0.0-alpha.N  预发布
```

### Step 0.5 — API 稳定性承诺（30 分钟）

在 `docs/stability.md` 明确：

```
稳定（SemVer 保证）:
  * Tool.name
  * Tool.input_schema (JSON Schema)
  * Tool.return type (TextContent / structured)
  * ScopeGuard.ensure() 签名
  * CLI 参数（redteam-mcp serve/doctor/list-tools）

不稳定（可能任意变更）:
  * 内部 executor.py 实现
  * 日志格式
  * 内部 parser
  * 未公开的 config 字段

弃用流程:
  1. 标记 DeprecationWarning
  2. 维持 2 个 minor release
  3. 下一个 major release 删除
```

这样用户写 plugin 才能放心。

---

## Phase 0 最终验收

跑一遍 `scripts/full_verify.py` + 以下新增检查：

```
[ ] pytest 全绿（3 OS × 3 Python = 9 个组合）
[ ] ruff check 0 警告
[ ] mypy strict 模式 0 错误
[ ] README 无 "redteam" 字样
[ ] LICENSE 过 OpenSSF Scorecard
[ ] pip install kestrel-mcp 成功
[ ] docker run ghcr.io/xxx/kestrel-mcp:latest 成功
[ ] 三个 MCP host（Cursor/Claude/Cline）config 例子都验证能跑
```

---

# Part 4 — 跨平台支持矩阵

## 核心服务器（Python）

| OS | 架构 | 测试? | 主要风险 |
|----|------|------|---------|
| Windows 10+ | x64 | ✅ CI | subprocess 编码、路径分隔符 |
| Windows 11 ARM | arm64 | ⚠️ 手测 | Python ARM wheel |
| Linux (glibc) | x64 | ✅ CI | - |
| Linux (glibc) | arm64 | ✅ CI | - |
| Linux (musl / Alpine) | x64 | ⚠️ docker | |
| macOS | x64 Intel | ✅ CI | - |
| macOS | arm64 Apple Silicon | ✅ CI | - |

## 下游工具（第三方）

这才是难点。每个工具有自己的平台矩阵。

### 处理策略：分层
1. **Tier A — 全平台 Go 工具**：nuclei / sliver / ligolo / subfinder
   - 上游提供 Linux / Windows / macOS binary
   - 我们的 installer 直接从 GitHub releases 拉
2. **Tier B — 仅 Linux / macOS**：Impacket / Responder / BloodHound
   - Windows 上需 WSL2 或 Docker
   - 明确告知用户
3. **Tier C — 需 GUI**：Havoc Client / Caido GUI
   - 不走 MCP，通过 `xxx_generate_hint` tool 返回操作步骤

详见 [附录 A](#附录-a--50-工具矩阵)。

## 开源后其他系统怎么办？

### Linux 用户
```bash
# Ubuntu/Debian
curl -fsSL https://kestrel-mcp.dev/install.sh | bash
# 或 apt
apt install kestrel-mcp

# Arch
yay -S kestrel-mcp

# Docker（推荐）
docker run -v ~/.config/kestrel:/config ghcr.io/xxx/kestrel-mcp
```

### macOS 用户
```bash
# Homebrew
brew install kestrel-mcp

# 或 pip
pip install kestrel-mcp
```

### Windows 用户
```powershell
# winget（未来）
winget install kestrel-mcp

# 或 pip
pip install kestrel-mcp
```

### 工具自动下载
```bash
# 一次性帮用户下载所有需要的第三方二进制
kestrel-mcp install-tools --set recon
kestrel-mcp install-tools --set c2 --platform linux-amd64
kestrel-mcp install-tools --all
```

`install-tools` 命令读 `tools_manifest.yaml`：
```yaml
- name: nuclei
  upstream: projectdiscovery/nuclei
  version: v3.8.0
  platforms:
    windows-amd64: nuclei_3.8.0_windows_amd64.zip
    linux-amd64: nuclei_3.8.0_linux_amd64.zip
    darwin-arm64: nuclei_3.8.0_macOS_arm64.zip
  checksum_url: https://github.com/projectdiscovery/nuclei/releases/download/v3.8.0/nuclei_3.8.0_checksums.txt
  post_install: ["nuclei -update-templates"]
```

---

# Part 5 — 工具生态扩展（Phase 1）

> **目标**: 从 6 个 → **20 个**（Phase 1 结束）→ **50 个**（Phase 3 结束）

详细 50 个工具见 [附录 A](#附录-a--50-工具矩阵)。

## Phase 1（Week 2-4）优先加的 15 个

按"渗透 kill chain"顺序：

| # | 工具 | 阶段 | 跨平台 | Priority |
|---|------|------|-------|---------|
| 1 | **subfinder** | Recon | ✅ all | P0 |
| 2 | **amass** | Recon | ✅ all | P0 |
| 3 | **httpx** | Recon | ✅ all | P0 |
| 4 | **naabu** | Scan | ✅ all | P0 |
| 5 | **nmap** | Scan | ✅ all | P0 |
| 6 | **katana** | Web | ✅ all | P1 |
| 7 | **ffuf** | Web | ✅ all | P0 |
| 8 | **feroxbuster** | Web | ✅ all | P1 |
| 9 | **sqlmap** | Web | ✅ py | P0 |
| 10 | **dalfox** | Web XSS | ✅ all | P1 |
| 11 | **metasploit-rpc** | Exploit | ⚠️ Linux 优先 | P0 |
| 12 | **impacket-scripts** | AD | ⚠️ Linux | P0 |
| 13 | **NetExec** | AD | ✅ py | P0 |
| 14 | **hashcat** | Cracking | ✅ all (需 GPU 驱动) | P1 |
| 15 | **BloodHound-CE** | AD | ⚠️ Docker | P1 |

## 每个 tool wrapper 的标准颗粒度

一个 tool wrapper = 一个 Python 文件 = **~200 行**。包含：

1. **Docstring**: 工具作用、官方来源、license 兼容性
2. **配置块定义**: 默认 binary 路径、版本要求
3. **所有 ToolSpec**: 每个对 LLM 暴露的功能（3~8 个）
4. **handler 实现**: 调用 `run_command()` + 解析输出
5. **输出 parser**: 从 stdout 提取结构化字段
6. **单元测试**: 至少 3 个（mock 子进程）

模板见 [附录 B](#附录-b--toolskillplugin-模板)。

## 每 tool 交付清单

```
[ ] src/kestrel_mcp/tools/<category>/<tool>_tool.py        核心实现
[ ] tests/unit/tools/test_<tool>.py                         单测
[ ] docs/tools/<tool>.md                                    文档
[ ] examples/<tool>_example.md                              cursor 里怎么说
[ ] 更新 docs/index.md 的工具清单
[ ] 更新 CTF_CHEATSHEET.md
[ ] 更新 tools_manifest.yaml（installer 用）
[ ] 一条 PR description，解释加这个工具的理由
```

---

# Part 6 — Plugin 系统（Phase 2）

## 为什么要 plugin 而不是一直硬编码

- 社区贡献 tool 不用 fork 主仓库
- 用户可以自己加私有 tool（不想 PR）
- 官方 tools 和社区 tools 生命周期独立

## 设计目标

```
目标 1: 写 plugin 不需要理解 MCP 协议，只需 30 行 Python
目标 2: plugin 可以是单文件 .py，也可以是 pip 包
目标 3: plugin 共享 ScopeGuard / executor / logging
目标 4: 不信任 plugin（跑在子进程里，不污染核心）
```

## Plugin 加载机制

```python
# 1. 约定目录加载
~/.config/kestrel-mcp/plugins/*.py

# 2. pip entry_points 加载
# plugin 包 pyproject.toml:
[project.entry-points."kestrel_mcp.plugins"]
my_tool = "my_plugin.module:MyToolModule"

# 3. config.yaml 显式启用
plugins:
  - kestrel_plugin_awesome
  - path: /my/local/plugin.py
```

## Plugin 开发者 API

```python
# my_plugin.py
from kestrel_mcp.plugins import Plugin, tool, scope_required

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"

    @tool(
        description="Scan with my_custom_scanner",
        dangerous=True,
    )
    @scope_required("target")
    async def my_custom_scan(self, target: str, depth: int = 1):
        result = await self.run_cmd(["my-scanner", "-t", target, "-d", str(depth)])
        return self.parse(result.stdout)
```

**30 行。**

## Plugin 分发

- **官方 marketplace**: github.com/kestrel-mcp/plugins
- **pip 安装**: `pip install kestrel-plugin-xyz`
- **本地开发**: `kestrel-mcp plugins add /path/to/plugin.py`

---

# Part 7 — Skills 与 MCP Tools 的关系

## 两种"Skills"需要区分

### 1. Cursor Agent Skills（你之前在 `.cursor/skills-cursor/` 做的）
- 目的：**告诉 Cursor 的 LLM 怎么手动用某个工具**
- 触发：用户的自然语言匹配 description
- 内容：Markdown 文档（命令示例、场景）
- **不涉及** MCP 协议

### 2. MCP Tools（本项目的核心）
- 目的：**让 LLM 直接调用工具**
- 触发：LLM 主动选择 tool + 填参数
- 内容：带 JSON Schema 的 Python handler
- **就是** MCP 协议

## 如何协同

```
用户说: "帮我扫 10.10.10.5 的漏洞"
  ↓
① Cursor Agent Skills 匹配 "nuclei-scan" skill
  → 读 SKILL.md 知道大致怎么做
  ↓
② LLM 决定调 MCP tool: nuclei_scan
  → 填参数 {"targets": ["10.10.10.5"]}
  ↓
③ MCP server 执行:
  → ScopeGuard 检查
  → 运行 nuclei.exe
  → 返回结构化 findings
  ↓
④ LLM 根据结果回答
```

## Phase 1-5 里 Skills 怎么处理

- **每个 tool wrapper 的同时，写一份 Skill MD**
- Skill MD 放在 `examples/skills/` 下
- 用户可选把它们复制到自己的 Cursor skills 目录
- 或者打包到 `kestrel-mcp-skills` 独立包，`kestrel-mcp install-skills` 一键部署

模板见 [附录 B](#附录-b--toolskillplugin-模板)。

---

# Part 8 — 测试、质量、安全审计（Phase 3）

## 测试分层

### L1 — 单元测试（unit/）
- 每个 tool handler 用 mock subprocess
- 测 parser 边界条件
- 测 scope_guard 各种组合
- **覆盖率目标: 80%+**

### L2 — 集成测试（integration/）
- 跑真实子进程（echo、dir 等）
- 测完整 MCP server init → tool call → response 链路
- 每个 OS 跑一次

### L3 — e2e 测试（e2e/）
- Docker 里跑真实目标（vulnerable app，如 DVWA）
- 测完整攻击流程：subfinder → nuclei → sqlmap
- 只在 release 前跑

## 质量守卫

```
每个 commit 必须通过:
  ✅ ruff check (lint)
  ✅ ruff format --check (style)
  ✅ mypy --strict (type)
  ✅ pytest tests/unit (80%+ cov)
  ✅ bandit security scan
  ✅ no secrets (trufflehog)

每周自动:
  ✅ CodeQL security scan
  ✅ dependabot 依赖更新
  ✅ license compliance (Apache 兼容性)

每 release 前:
  ✅ 完整 e2e 测试
  ✅ docker image 扫描（trivy）
  ✅ SBOM 生成（syft）
  ✅ 签名（cosign）
```

## 安全审计清单

因为这是进攻性工具，审计更严格：

```
[ ] 所有 subprocess 用 argv list，无 shell=True
[ ] 所有用户输入过 JSON Schema 验证
[ ] ScopeGuard 100% 覆盖所有 dangerous tool
[ ] 审计日志不含 API key / password
[ ] 临时文件清理
[ ] 子进程 timeout 强制生效
[ ] 输出大小限制
[ ] 无命令注入（模糊测试）
[ ] 无路径遍历
[ ] CLI 参数不被 flag injection
```

---

# Part 9 — 文档与发布（Phase 4）

## 文档层次

```
入口层（README.md）         30 秒了解项目
快速开始（QUICKSTART.md）    10 分钟跑起来
教程（docs/tutorials/）      30 分钟 - 2 小时系列
参考（docs/reference/）      字典式查
深度（docs/internals/）      架构、设计决策
贡献（CONTRIBUTING.md）       怎么加 tool/plugin
FAQ                        常见问题
CHANGELOG                   版本历史
```

## 文档站点

**MkDocs Material** 或 **Docusaurus**，部署到 GitHub Pages。

URL 结构：
```
kestrel-mcp.dev/
├── /                    README 首页
├── /quickstart
├── /tutorials/
│   ├── /first-scan
│   ├── /ctf-walkthrough
│   └── /red-team-engagement
├── /reference/
│   ├── /tools/ffuf      (每个 tool 一页)
│   ├── /tools/nuclei
│   └── ...
├── /plugins/
│   ├── /authoring
│   └── /registry
├── /contributing
└── /faq
```

## 发布清单（v1.0）

```
1 周前：
  [ ] 所有 tests 在 3 OS 上绿
  [ ] 文档站点 100% 完成
  [ ] 5 个 blog post 写好（存为 draft）
  [ ] 3 个 demo 视频录好
  [ ] Discord 服务器搭好

发布日：
  [ ] git tag v1.0.0
  [ ] GitHub Release（含完整 changelog）
  [ ] PyPI 发布
  [ ] Docker Hub / GHCR 发布
  [ ] Homebrew tap
  [ ] 发 Hacker News "Show HN"
  [ ] 发 Twitter / X
  [ ] 发 r/netsec / r/redteamsec
  [ ] 发 LinkedIn
  [ ] 发公众号（中文）

发布后 1 周：
  [ ] 回每一个 issue
  [ ] 每日更新 changelog
  [ ] 如有 critical bug, hotfix v1.0.1
```

---

# Part 10 — 社区与推广（Phase 5）

## 推广渠道矩阵

| 渠道 | 受众 | 频率 | 内容 |
|------|------|-----|------|
| Twitter / X | 国际安全圈 | 2-3x/周 | 技术 tweet + demo gif |
| r/netsec | 英文专业 | 1x/月 | writeup，严禁自卖自夸 |
| r/redteamsec | 红队 | 1x/月 | 技术 deep dive |
| Hacker News | 广泛技术 | 2-3x/年 | 重大版本发布 |
| DEFCON Arsenal | 顶级曝光 | 1x/年 | 现场 demo |
| BlackHat Tools Arsenal | 同上 | 1x/年 | |
| 公众号 / 知乎 | 国内 | 1-2x/周 | 中文教程 |
| B站 | 国内视频 | 1x/周 | 实战演示 |
| Discord | 忠实用户 | 持续 | 答疑 + 预告 |
| Email newsletter | 专业用户 | 1x/月 | 深度内容 |

## 社区运营原则

```
1. Issue 必回（< 48h）
2. PR 必 review（< 7 天）
3. 永远不骂社区成员，即使他们错了
4. 恶意用户直接 ban
5. 每周 1 个公开 office hour（Discord voice）
6. 每月 1 次线上 meetup
7. 明星贡献者 pin 上首页
```

## Contributor funnel

```
浏览者         (Star)
  ↓
使用者         (install)
  ↓
反馈者         (open issue)
  ↓
贡献者         (send PR)
  ↓
核心贡献者     (merge rights)
  ↓
Maintainer
```

每一层都要有明确的升级路径。

---

# Part 11 — 商业化路径（可选）

## 选项 A — 纯 OSS（不商业化）

- 完全开源
- 不接受 sponsorship（避免利益冲突）
- 适合：把它当作 portfolio 项目

## 选项 B — GitHub Sponsors + 咨询

- 开放 Sponsor 按钮
- 提供付费咨询（pentest engagement / 培训）
- Revenue 预期: $0-5k/月（增长取决于社区规模）

## 选项 C — Open Core 模式

- **OSS 版**: 所有 tool wrapper + plugin 框架
- **Pro 版（闭源）**:
  - 多操作员协作
  - 企业 SIEM 集成（Splunk / ELK）
  - 合规报告自动化
  - SSO / SAML
  - 私有 plugin marketplace
- Pricing: $99/月/席位
- Revenue 预期（12 个月）: $0-50k ARR

## 选项 D — SaaS

- 完整托管服务
- 风险最高（法律责任）
- 只建议公司化后再考虑

**我的建议**: 从 A 或 B 开始，6 个月后根据反馈决定要不要 C。

---

# Part 12 — 风险清单

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 中国管控部分功能 | 🟡 中 | 中 | 地区编译 flag，敏感 tool 单独 repo |
| 被媒体攻击 | 🟢 低 | 高 | 提前 security researcher 背书 |
| 被恶意攻击者利用 | 🟡 中 | 中 | ScopeGuard + 审计 + 教育 |
| 上游工具 breaking change | 🔴 高 | 中 | 版本 pinning + CI matrix |
| 维护负担 | 🔴 高 | 高 | Plugin 系统 + community core team |
| 商标纠纷 | 🟢 低 | 低 | 选择独特名字 + 搜索 check |
| 安全漏洞 | 🟡 中 | 高 | 定期 audit + bug bounty |
| 你个人精力耗尽 | 🟡 中 | 高 | 明确 v1.0 后节奏，不要 overextend |

---

# 附录 A — 50+ 工具矩阵

**列名说明**：
- `Cat`: Category（recon/scan/web/expl/c2/post/crack）
- `Lang`: 实现语言（Go/Py/Rust/C/Ruby）
- `Lic`: License（MIT/GPL/BSD/Apache/Commercial）
- `W/L/M`: Windows / Linux / macOS 支持（✅ 有 binary, ⚠️ 需编译/WSL, ❌ 不支持）
- `Size`: 单文件二进制大小
- `Install`: 官方下载

## Tier 1 — 必须集成（Phase 1，15 个）

| # | Tool | Cat | Lang | Lic | W | L | M | Size | Upstream |
|---|------|-----|------|-----|---|---|---|------|----------|
| 1 | **Shodan** (已有) | recon | API | Comm | ✅ | ✅ | ✅ | - | https://account.shodan.io |
| 2 | **Nuclei** (已有) | scan | Go | MIT | ✅ | ✅ | ✅ | 120MB | github.com/projectdiscovery/nuclei |
| 3 | **Caido** (已有) | web | Rust | MIT+Comm | ✅ | ✅ | ✅ | 220MB | caido.io |
| 4 | **Ligolo-ng** (已有) | pivot | Go | MIT | ✅ | ✅ | ✅ | 20MB | github.com/nicocha30/ligolo-ng |
| 5 | **Sliver** (已有) | c2 | Go | GPL | ✅ | ✅ | ✅ | 295MB | github.com/BishopFox/sliver |
| 6 | **Evilginx** (已有) | phish | Go | BSD | ✅ | ✅ | ✅ | 15MB | github.com/kgretzky/evilginx2 |
| 7 | **Havoc** (可选) | c2 | Go+C | BSD | ⚠️cgo | ✅ | ⚠️ | 编译 | github.com/HavocFramework/Havoc |
| 8 | **subfinder** | recon | Go | MIT | ✅ | ✅ | ✅ | 20MB | github.com/projectdiscovery/subfinder |
| 9 | **amass** | recon | Go | Apache | ✅ | ✅ | ✅ | 30MB | github.com/owasp-amass/amass |
| 10 | **httpx** | recon | Go | MIT | ✅ | ✅ | ✅ | 15MB | github.com/projectdiscovery/httpx |
| 11 | **naabu** | scan | Go | MIT | ⚠️libpcap | ✅ | ✅ | 10MB | github.com/projectdiscovery/naabu |
| 12 | **nmap** | scan | C | GPL | ✅ | ✅ | ✅ | 30MB | nmap.org |
| 13 | **katana** | web | Go | MIT | ✅ | ✅ | ✅ | 30MB | github.com/projectdiscovery/katana |
| 14 | **ffuf** | web | Go | MIT | ✅ | ✅ | ✅ | 10MB | github.com/ffuf/ffuf |
| 15 | **sqlmap** | web | Py | GPL | ✅ | ✅ | ✅ | pip | github.com/sqlmapproject/sqlmap |

## Tier 2 — 强烈建议（Phase 2，15 个）

| # | Tool | Cat | Lang | Lic | W | L | M | Size |
|---|------|-----|------|-----|---|---|---|------|
| 16 | **feroxbuster** | web | Rust | MIT | ✅ | ✅ | ✅ | 10MB |
| 17 | **gobuster** | web | Go | Apache | ✅ | ✅ | ✅ | 10MB |
| 18 | **dalfox** | web | Go | MIT | ✅ | ✅ | ✅ | 15MB |
| 19 | **arjun** | web | Py | BSD | ✅ | ✅ | ✅ | pip |
| 20 | **wpscan** | web | Ruby | GPL | ⚠️ | ✅ | ✅ | gem |
| 21 | **nikto** | web | Perl | GPL | ⚠️ | ✅ | ✅ | git |
| 22 | **Metasploit RPC** | expl | Ruby | BSD | ⚠️WSL | ✅ | ✅ | 1GB |
| 23 | **Impacket** | AD | Py | Apache | ✅ | ✅ | ✅ | pip |
| 24 | **NetExec (nxc)** | AD | Py | BSD | ✅ | ✅ | ✅ | pip |
| 25 | **Responder** | LLMNR | Py | GPL | ⚠️ | ✅ | ⚠️ | git |
| 26 | **BloodHound CE** | AD | TS+Py | GPL | ⚠️Docker | ✅ | ✅ | Docker |
| 27 | **SharpHound** | AD | C# | GPL | ✅ | ⚠️mono | ⚠️ | 1MB |
| 28 | **Rubeus** | AD | C# | BSD | ✅ | ⚠️ | ⚠️ | 1MB |
| 29 | **Kerbrute** | AD | Go | MIT | ✅ | ✅ | ✅ | 5MB |
| 30 | **Certipy** | AD | Py | MIT | ✅ | ✅ | ✅ | pip |

## Tier 3 — 完整武器库（Phase 3，20 个）

| # | Tool | Cat | 备注 |
|---|------|-----|------|
| 31 | hashcat | crack | 大体积（GPU 驱动依赖） |
| 32 | john | crack | JtR |
| 33 | hydra | brute | 在线密码爆破 |
| 34 | theHarvester | osint | 邮箱/子域 OSINT |
| 35 | SpiderFoot | osint | OSINT 自动化 |
| 36 | Sherlock | osint | 用户名跨站 |
| 37 | holehe | osint | 邮箱关联账户 |
| 38 | GHunt | osint | Google 账户 OSINT |
| 39 | dnsrecon | recon | DNS 枚举 |
| 40 | dnstwist | recon | 域名 typosquat |
| 41 | masscan | scan | 10M pps 扫描 |
| 42 | rustscan | scan | Rust 快速扫 |
| 43 | nuclei-fuzzing | web | DAST 补丁 |
| 44 | Burp Suite 社区 CLI | web | 有限 |
| 45 | msfvenom | expl | payload 生成 |
| 46 | **Mythic C2** | c2 | Docker C2 |
| 47 | **Havoc** (真编译) | c2 | |
| 48 | **garak** | AI sec | LLM 红队 |
| 49 | **PyRIT** | AI sec | 微软 LLM 红队 |
| 50 | **promptmap** | AI sec | prompt 注入 |

---

# 附录 B — Tool/Skill/Plugin 模板

## Tool Wrapper 模板（完整可用）

```python
# src/kestrel_mcp/tools/recon/subfinder_tool.py
"""subfinder tool — passive subdomain enumeration.

Upstream: github.com/projectdiscovery/subfinder (MIT License)
Binary:   subfinder.exe / subfinder
Platforms: Linux / macOS / Windows (all amd64/arm64)

Exposed MCP tools:
    * subfinder_enum       run full enumeration
    * subfinder_version    report installed version
"""

from __future__ import annotations

import json
from typing import Any

from ...core.config import Settings
from ...core.executor import resolve_binary, run_command
from ...core.logging import audit_event
from ...core.security import ScopeGuard
from ..base import ToolModule, ToolResult, ToolSpec


class SubfinderModule(ToolModule):
    id = "subfinder"

    def __init__(self, settings: Settings, scope_guard: ScopeGuard) -> None:
        super().__init__(settings, scope_guard)
        block = settings.tools.subfinder
        self._binary_hint: str | None = getattr(block, "binary", None)

    def _binary(self) -> str:
        return resolve_binary(self._binary_hint, "subfinder")

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="subfinder_enum",
                description=(
                    "Enumerate subdomains of a root domain using passive sources "
                    "(Shodan, VirusTotal, CT logs, etc.). Target MUST be within "
                    "authorized scope."
                ),
                input_schema={
                    "type": "object",
                    "required": ["domain"],
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Root domain, e.g. 'example.com'",
                        },
                        "all_sources": {"type": "boolean", "default": False},
                        "silent": {"type": "boolean", "default": True},
                        "recursive": {"type": "boolean", "default": False},
                        "timeout_sec": {"type": "integer", "minimum": 10, "maximum": 1800},
                    },
                    "additionalProperties": False,
                },
                handler=self._handle_enum,
                dangerous=True,
                requires_scope_field="domain",
                tags=["recon", "passive"],
            ),
            ToolSpec(
                name="subfinder_version",
                description="Report the installed subfinder version.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=self._handle_version,
                tags=["meta"],
            ),
        ]

    async def _handle_enum(self, arguments: dict[str, Any]) -> ToolResult:
        domain = arguments["domain"]
        binary = self._binary()
        argv = [binary, "-d", domain, "-oJ"]
        if arguments.get("all_sources"):
            argv.append("-all")
        if arguments.get("silent", True):
            argv.append("-silent")
        if arguments.get("recursive"):
            argv.append("-recursive")

        timeout = int(arguments.get("timeout_sec") or self.settings.execution.timeout_sec)

        if self.settings.security.dry_run:
            return ToolResult(
                text=f"[dry-run] would run: {' '.join(argv)}",
                structured={"dry_run": True, "argv": argv},
            )

        result = await run_command(
            argv,
            timeout_sec=timeout,
            max_output_bytes=self.settings.execution.max_output_bytes,
        )
        subs = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        audit_event(
            self.log,
            "subfinder.enum",
            domain=domain,
            count=len(subs),
            duration_sec=result.duration_sec,
        )
        return ToolResult(
            text=f"Subfinder found {len(subs)} subdomain(s) of {domain}.",
            structured={
                "domain": domain,
                "count": len(subs),
                "subdomains": [s.get("host") for s in subs],
                "raw": subs,
            },
            is_error=not result.ok,
        )

    async def _handle_version(self, _args: dict[str, Any]) -> ToolResult:
        binary = self._binary()
        result = await run_command([binary, "-version"], timeout_sec=30, max_output_bytes=64_000)
        return ToolResult(
            text=(result.stdout or result.stderr).strip(),
            structured={"raw": result.stdout or result.stderr},
            is_error=not result.ok,
        )
```

## Unit Test 模板

```python
# tests/unit/tools/test_subfinder.py
import pytest
from unittest.mock import AsyncMock, patch

from kestrel_mcp.core.config import Settings
from kestrel_mcp.core.security import ScopeGuard
from kestrel_mcp.tools.recon.subfinder_tool import SubfinderModule


@pytest.fixture
def module():
    settings = Settings()
    settings.tools.subfinder.enabled = True
    settings.tools.subfinder.binary = "/fake/subfinder"
    guard = ScopeGuard(["*.example.com"])
    return SubfinderModule(settings, guard)


async def test_enum_happy_path(module):
    mock_result = AsyncMock()
    mock_result.ok = True
    mock_result.stdout = '{"host":"a.example.com"}\n{"host":"b.example.com"}\n'
    mock_result.duration_sec = 1.0
    mock_result.truncated = False

    with patch("kestrel_mcp.tools.recon.subfinder_tool.run_command", return_value=mock_result):
        spec = next(s for s in module.specs() if s.name == "subfinder_enum")
        result = await spec.handler({"domain": "example.com"})
    assert not result.is_error
    assert result.structured["count"] == 2
    assert "a.example.com" in result.structured["subdomains"]


async def test_enum_refuses_out_of_scope(module):
    spec = next(s for s in module.specs() if s.name == "subfinder_enum")
    # Simulate scope enforcement - called from server before handler
    with pytest.raises(Exception):
        module.scope_guard.ensure("evil.com", tool_name="subfinder_enum")
```

## Skill MD 模板

```markdown
<!-- examples/skills/subfinder.SKILL.md -->
---
name: subfinder-skill
description: Passive subdomain enumeration with subfinder via kestrel-mcp.
---

# Subfinder via Kestrel MCP

Use when the user asks to enumerate subdomains of a target domain.

## When to trigger

- "find subdomains of X"
- "enumerate X.com"
- "what subdomains does acme.com have"

## What to do

1. Call `subfinder_enum` with the root domain
2. If results are few (<5), suggest `all_sources: true` for deeper scan
3. Summarize top 10 + total count

## Sample prompts

- "list all subdomains of acme.com"
- "deep enumerate *.acme.com including CT logs"

## Safety note

Target must be in authorized_scope. Subfinder is passive so it doesn't send
packets to the target, but it does query third-party sources.
```

## Plugin 最小示例

```python
# example_plugin/my_plugin.py
from kestrel_mcp.plugins import Plugin, tool, scope_required

class HelloPlugin(Plugin):
    name = "hello_plugin"
    version = "0.1.0"

    @tool(description="Say hello to a target host.")
    @scope_required("host")
    async def hello(self, host: str):
        result = await self.run_cmd(["ping", "-c", "1", host])
        return {"reachable": result.ok, "host": host}
```

---

# 附录 C — CI/CD 配置模板

## .github/workflows/ci.yml

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/
      - run: mypy src/

  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python: ['3.10', '3.11', '3.12']
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '${{ matrix.python }}' }
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit -v --cov=src/kestrel_mcp --cov-report=xml
      - uses: codecov/codecov-action@v4

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with: { scan-type: 'fs', format: 'sarif', output: 'trivy.sarif' }
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: 'trivy.sarif' }
```

## Dockerfile

```dockerfile
FROM python:3.12-slim AS base

# System deps for tools that need them
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Non-root for security
RUN useradd -m -u 1000 kestrel
USER kestrel

ENV REDTEAM_MCP_SECURITY__AUTHORIZED_SCOPE="" \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["kestrel-mcp"]
CMD ["serve"]
```

---

# 🚦 我现在在这份文档里要你做的决策

在我动手前，**你必须拍板 4 个决策**，不然地基会返工：

## 决策 1 — 项目名字

```
[ ] A. kestrel-mcp      (茶隼，我推荐)
[ ] B. armory           (军械库)
[ ] C. redwing          (红翼)
[ ] D. 其他: ______     (你提)
[ ] E. 保留 redteam-mcp (不改)
```

## 决策 2 — License

```
[ ] A. Apache 2.0 + Responsible Use Addendum (我推荐)
[ ] B. MIT (当前)
[ ] C. GPL v3 (更强 copyleft)
[ ] D. BSD 3-clause (Evilginx/Havoc 风格)
```

## 决策 3 — 商业化路线

```
[ ] A. 纯 OSS，不考虑盈利 (精力最少)
[ ] B. OSS + Sponsor/咨询 (我推荐)
[ ] C. Open Core (OSS + 闭源企业版)
[ ] D. 以后再说，先做社区
```

## 决策 4 — 第一个里程碑（v1.0）的工具数量

```
[ ] A. 15 个 (Phase 1 结束 = v1.0)     ← 2 周
[ ] B. 25 个 (Phase 1+2 = v1.0)         ← 4 周
[ ] C. 50 个 (完整武器库 = v1.0)        ← 8 周
```

---

## 🎬 下一步（你确认决策后我做）

1. 按决策 1 改名 + 调整仓库结构
2. 按决策 2 换 License + 加 RESPONSIBLE_USE.md / CONTRIBUTING / CODE_OF_CONDUCT / SECURITY
3. 搭 CI/CD（3 个 workflow）
4. 按决策 4 开始写 tool wrapper（每天 3-5 个）

**你回复**: `1: X, 2: X, 3: X, 4: X` 我立刻开干。

---

*这份 MASTER_PLAN.md 是活文档。每完成一个里程碑就更新 status，每改一次决策都留痕。*
