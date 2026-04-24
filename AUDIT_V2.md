# CODEBASE AUDIT V2

> 第二轮审查。基于 [CTF_ECOSYSTEM_RESEARCH.md](./CTF_ECOSYSTEM_RESEARCH.md) 的真网络调研。
> 目的：找 **AUDIT.md（v1）没发现**的 gap。
> 每个 gap 带证据（引用或竞品对照），打严重度，标 RFC 归属。

**Audit date**: 2026-04-21 (v2)
**Previous**: [AUDIT.md](./AUDIT.md) (v1)
**Scope change from v1**:
- v1 只盘点内部代码
- v2 带着 10 个竞品 + 5 个学术 benchmark + 8 个工程实践 做对照

---

## Part 0 — v1 的执行状态复盘

v1 列了 13 个 D-gap（D-1..D-13）+ 10 个 trap。现在状态：

| Gap | 状态 | RFC |
|-----|------|-----|
| D-1 包名 redteam_mcp ↔ kestrel-mcp | OPEN | RFC-H01 计划 |
| D-2 Settings env 脆弱 | RESOLVED(partial) | RFC-001 + `env_ignore_empty` |
| D-3 Scope 双路径没收拢 | RESOLVED | Sprint 2 的 `RequestContext.ensure_scope` + server `_check_scope` |
| D-4 Plugin 系统口头约定 | OPEN | RFC-Plugin（未分配号） |
| D-5 Alembic tzdata 坑 | OPEN | RFC-002 的 CI workflow 已包含 |
| D-6 Nuclei 解析脆弱 | OPEN | 无 RFC |
| D-7 Sliver 表格解析脆弱 | OPEN | 无 RFC |
| D-8 无 CI | OPEN | RFC-002 |
| D-9 Secrets 明文 | PARTIAL | RFC-003（Credential Store）— 但只做 engagement credential，没做 API key |
| D-10 无 CD | OPEN | RFC-H02 |
| D-11 没文档站点 | OPEN | RFC-H03 |
| D-12 5 个工具缺 rich description | OPEN | RFC-B02 |
| D-13 Threat model 无 status tracking | OPEN | RFC-B03 |

**v1 列的 10 个 trap** → 都进了 AGENT_EXECUTION_PROTOCOL §R1-R7 硬规则，基本覆盖。

**v1 漏掉的**：全部集中在「和外部生态对比我们缺什么」这个方向。下面是 v2 的增补。

---

## Part 1 — v2 新增：竞品对比得出的 gap

### V-C1 | 多模型混用策略缺失（Mixed-Model Routing）

**证据**: [Neurogrid CTF 第 5 名 writeup](https://0ca.github.io/ctf/ai/security/2025/11/28/neurogrid-ctf-writeup.html)
- 0ca 用 BoxPwnr 时：免费 Grok-4.1-fast 扫 8 个水题 → Gemini-3-pro 解 10 个 → Claude-Sonnet-4.5 解 10 个 → GPT-5.1-codex 解最后 4 个硬题
- **混用比单模型成功率高出一倍以上**，成本降低 70%

**我们现状**: MCP server 无模型偏好；任一 LLM 接入都按同样接口跑 → 用户要手动选。

**影响**:
- Pro 版：低，专业用户自己会选
- Team 版：**高**，比赛要拼速度和成本

**RFC 建议**: 新增 `RFC-V01: Model routing policy` — 在 `ToolSpec` 加 `preferred_model_tier: "easy"|"medium"|"hard"`；dispatcher 按 tool 标签选模型。**这是新 concept，需要引入 LLM 抽象层。**

---

### V-C2 | Attack graph / solution replay 缺失

**证据**: [BoxPwnr](https://github.com/0ca/BoxPwnr)
- 每个挑战生成 attack graph + report.md + 可交互 replay HTML
- [示例](https://0ca.github.io/BoxPwnr-Traces/replayer/replay.html?trace=htb_ctf/...)

**我们现状**:
- `ToolInvocation` 表已记录完整调用链（Sprint 1 Domain）
- 但没有 UI 层把这些串成可视化
- RFC-E01 计划 Cytoscape "静态攻击链"，但没规划 replay

**影响**:
- Pro 版：中，客户要报告附件
- Team 版：**极高**，赛后复盘的核心资产

**RFC 建议**:
- 修订 RFC-E01 增加 "replay mode"
- 新增 `RFC-V02: Writeup / replay export` — 给定 engagement，一键导出 markdown + html 回放包

---

### V-C3 | Writeup export 自动化缺失

**证据**: [BoxPwnr-Traces repo](https://github.com/0ca/BoxPwnr-Traces) 作为 2024-11 Neurogrid 的**交付物**

**我们现状**:
- `generate_pentest_report` 生成 markdown，但内容靠 LLM 自己拼
- 没有从 `ToolInvocation + Finding + Artifact` 结构化导出
- 比赛结束后队员想回头看「Claude 第 17 步为什么那样 reason」→ 没工具

**影响**: 同 V-C2，**Team 版高**

**RFC 建议**: `RFC-V02` 合并到 V-C2 里

---

### V-C4 | Tool shadowing 防护缺失

**证据**: [arxiv 2511.15998 "Hiding in the AI Traffic"](https://arxiv.org/html/2511.15998v1) + [redteams.ai MCP Tool Shadowing](https://redteams.ai/topics/walkthroughs/attacks/mcp-tool-shadowing)
- 多 MCP server 注册同名工具 → agent 可能调恶意版本
- 未来接社区 plugin 时必须防

**我们现状**:
- `tools/__init__.py::load_modules` 静态加载，没命名空间校验
- `EngagementModule` 的 16 个 tool 命名是 engagement_*, scope_*, target_*, finding_* — 运气好没碰撞
- 未来加外部 MCP server（比如 HexStrike 做 "connector"）会撞

**影响**: 中高（开源后更严重）

**RFC 建议**: `RFC-V03: Tool namespace + collision detection` — 强制 ToolSpec.name 前缀 `<module_id>_`，启动时 assert 唯一

---

### V-C5 | Subtask guidance 框架缺失

**证据**: [Cybench ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/3e9412a9c1d93810ef3ef7825115016b-Abstract-Conference.html)
- Cybench 40 题专业级挑战
- 纯自主 agent 在硬题上挣扎
- **加 subtask hints 显著提升成功率**
- 这是学界共识：**困难 CTF 必须拆子任务喂 agent**

**我们现状**:
- RFC 体系就是 "spec-driven subtask"，工程任务上已实现
- 但 **tool execution 时没有**：一次 `nuclei_scan` 失败，agent 自己重新规划
- 对本地小模型尤其致命

**影响**: Team 版极高（因为你说要给「傻瓜模型」用）

**RFC 建议**: `RFC-V04: Tool handler subtask system` — tool handler 可以返回 `PartialResult + suggested_next_steps`，agent 按 hint 继续

---

## Part 2 — v2 新增：团队协作缺失

### V-T1 | Obsidian Team Vault 模板缺失

**证据**: [BSwen 2026 教程](https://docs.bswen.com/blog/2026-03-23-sync-obsidian-vault-git-ai-collaboration/) / [Obsidian Teams 官方](https://help.obsidian.md/Teams/Syncing+for+teams)
- 团队共享笔记的**业界默认方案**
- Git + obsidian-git plugin + auto-commit 10min
- **双 vault 架构**：个人 vault + 团队 vault

**我们现状**:
- 零支持
- 用户要在 Cursor 里翻我们 Markdown

**影响**: Team 版中（quality-of-life）

**RFC 建议**: `RFC-T01: Team Vault bootstrap` — Team Edition ship 一个 `templates/team-vault/` 目录，内含：
- `engagements/<slug>/index.md` 自动从 engagement entity 生成
- `playbooks/` 目录含 Crypto/Web/Pwn/Rev workflow
- `patterns/` 目录做 pattern card 索引
- `.obsidian/` config 预填（不能提交 workspace.json）

---

### V-T2 | Vaultwarden 集成缺失

**证据**: [Vaultwarden github](https://github.com/dani-garcia/vaultwarden) / [NoPorts 2025 教程](https://www.noports.com/blog/vaultwarden-and-noports-shared-secrets-management)
- 团队凭证共享的事实标准
- 自托管免费，per-user 无费
- Bitwarden-compatible → 成熟客户端

**我们现状**:
- 有 `CredentialService` 本地加密，但**仅本机可见**
- 队内同步只能 git push 加密的 SQLite 数据库（脆弱）

**影响**: Team 版高（核心用例）

**RFC 建议**: `RFC-T02: Vaultwarden integration` — `CredentialService` 加 `sync_backend: local | vaultwarden_self_hosted`；配合 Team Edition 默认起一个 docker-compose 栈

---

### V-T3 | tmate 实时共享 shell 缺失

**证据**: [tmate.io](https://tmate.io) / [LinuxHandbook 教程](https://linuxhandbook.com/tmate/)
- Pair debugging 标准工具
- NAT 穿透，无需 SSH key 配置
- CTF 场景适合 "队员 A 在 pwn，B 过来一起看"

**我们现状**: 零

**影响**: Team 版中

**RFC 建议**: `RFC-T03: tmate session launcher` — MCP tool `team_share_shell(name)` 启动 tmate 并把连接串发到团队频道（通过 Discord/Slack webhook）

---

### V-T4 | Real-time state sync 缺失

**证据**: 团队协作的基本要求 + [MCP-based C2 研究](https://arxiv.org/html/2511.15998v1) 已证明 MCP 可做 "asynchronous parallel operations 实时情报共享"

**我们现状**:
- engagement DB 是 SQLite 本地
- 队友 A 加了 finding，B 看不到 until pull
- RFC-E03 有计划 "Event bus"，但是 Tier 3

**影响**: Team 版极高

**RFC 建议**: `RFC-T04: Realtime engagement sync` — 把 Engagement DB 后端可配置：
- `backend: sqlite`（Pro 默认，单人）
- `backend: postgres`（Team 共享）
- Event bus via Redis pub/sub 或 Postgres LISTEN/NOTIFY

**技术决策**: 引入 Postgres 依赖但 Pro 版 sqlite 保持默认（向后兼容）

---

### V-T5 | 队员归属 / contribution 模型缺失

**证据**: 所有 CTF 排行系统都有 "谁打出 first blood" 概念

**我们现状**:
- `Engagement.owners: list[UUID]` 存在但没实际用途
- `Finding.verified_by: UUID | None` 有了但 `discovered_by: Actor` 没有
- 无队内 scoreboard

**影响**: Team 版中高

**RFC 建议**: `RFC-T05: Actor contribution + scoreboard` — 扩 Finding / Flag 加 `discovered_by_actor`；Web UI 加 `/team/scoreboard`

---

## Part 3 — v2 新增：CTF 独特领域模型缺失

### V-D1 | CTF Domain: Match / Challenge / Flag 模型缺失

**证据**: 所有 CTF 比赛都是 `Match → Challenge → Flag` 三层

**我们现状**:
- Engagement 对应 Match（OK 可复用）
- **Target 对应 Challenge 但语义不匹配** — Challenge 是题目单元，Target 是 "资产"
- **完全没 Flag 实体**
- Finding 可以类比 Flag 但语义也偏（Finding=漏洞，Flag=战利品字符串）

**影响**: Team 版核心领域建模，**必须做**

**RFC 建议**: `RFC-T06: CTF domain extension` — 加:
```python
class Challenge(BaseModel):
    id: UUID
    engagement_id: UUID  # 所属 Match
    name: str  # "Whisper Vault"
    category: ChallengeCategory  # WEB / PWN / REV / CRYPTO / MISC / FORENSICS / OSINT
    difficulty: ChallengeDifficulty  # VERY_EASY / EASY / MEDIUM / HARD
    points: int | None
    status: ChallengeStatus  # unopened / working / solved / stuck
    assigned_to: UUID | None  # Actor
    start_time: datetime | None
    solve_time: datetime | None
    url: str | None  # 题目链接

class Flag(BaseModel):
    id: UUID
    challenge_id: UUID
    value: str  # 加密存储（复用 CredentialService seal）
    submitted_at: datetime | None
    submission_response: str | None  # 服务端 accept/reject 原文
    points_awarded: int | None
    submitted_by_actor: UUID
```

---

### V-D2 | Flag submission 自动化缺失

**证据**: HTB Neurogrid 的 MCP 集成里**flag 提交必须自动**；0ca 就是为此扩展了 BoxPwnr.htb_ctf_client

**我们现状**: 完全手工

**影响**: Team 版极高（速度优势直接来源）

**RFC 建议**: `RFC-T07: Flag submission adapters` — 每个平台一个 adapter:
- `HTBAdapter`
- `PicoCTFAdapter`
- `ChallengeNameAdapter` (通用)
- `CustomEndpointAdapter` (国内比赛 POST JSON)

---

### V-D3 | 赛前 bootstrap / 环境检查缺失

**证据**: HTB Season Tips 明确：**比赛前要做 VPN 测试、工具自检、nuclei-templates 更新等**

**我们现状**: 没这套

**影响**: Team 版中

**RFC 建议**: `RFC-T08: Pre-match bootstrap` — 命令 `kestrel team bootstrap --match htb-s10`:
1. `doctor` 全检
2. `nuclei -update-templates`
3. `subfinder -up -all`
4. VPN 连接测试（curl 目标 CIDR）
5. 打开 tmate / Discord webhook / Vaultwarden sync
6. 创建一个 Engagement=Match 实体

---

### V-D4 | "2-hour rule" 时间止损内置缺失

**证据**: [HTB 官方 Season tips](https://blazejgutowski.com/posts/htb-season-tips/)

**我们现状**: 无

**影响**: Team 版中

**RFC 建议**: `RFC-T09: Time budget per challenge` — Challenge 有 `time_budget: timedelta = 2h`；MCP tool 调用时 ctx 自动检查 `time_elapsed`，超 90% 时在 ToolResult 加 warning，超 100% 返回建议 "pivot"

---

### V-D5 | Nuclei / subfinder template refresh 自动化缺失

**证据**: 所有调研都反复强调这点

**我们现状**:
- `nuclei_update_templates` 手工触发
- `subfinder -up -all` 没包装

**影响**: Team 版低中（每周一次即可，能手动）

**RFC 建议**: 并入 `RFC-T08 bootstrap`

---

## Part 4 — v2 新增：AI 现实的 gap

### V-A1 | Local-model capability tier 缺失

**证据**: [HackingBuddyGPT arxiv](https://arxiv.org/html/2310.11409v6) — Llama3 只能 0-33% 成功率

**我们现状**: `LLM_GUIDANCE.md` 提到本地模型友好，但没具体的 **"这个 tool 对 Qwen-7B 不友好，跳过"** 机制

**影响**: Team 版中高（傻瓜模型是你明确的需求）

**RFC 建议**: `RFC-V05: Tool complexity tier` — `ToolSpec.complexity_tier: int` 0-5；配合 model tier，自动过滤

---

### V-A2 | Per-tool runtime budget 缺失

**证据**: RFC-004 rate-limit 只做 QPS，没做 single-call 最长 runtime

**我们现状**:
- `executor.run_command(timeout_sec=300)` 硬编码
- 无 CTF 场景下的自适应

**影响**: 中

**RFC 建议**: `RFC-V06: Per-tool soft timeout` — ToolSpec 加 `soft_timeout_sec`；跑到 80% 时推送 warning event 给 MCP client

---

### V-A3 | 成本追踪缺失

**证据**: [AutoPentest 实测 $96 / HTB 机](https://arxiv.org/pdf/2505.10321) 证明纯 AI 很烧钱

**我们现状**: 无

**影响**:
- Pro 版高（客户要账单）
- Team 版高（免费额度规划）

**RFC 建议**: `RFC-V07: Cost ledger` — 每次 ToolInvocation 记录估算成本（LLM tokens + subprocess sec）；engagement 汇总

---

### V-A4 | 防 prompt-injection (tool output untrust boundary) 未在代码执行

**证据**: [redteams.ai MCP Tool Shadowing](https://redteams.ai/topics/walkthroughs/attacks/mcp-tool-shadowing) — tool description 本身可被用做 prompt injection

**我们现状**:
- `LLM_GUIDANCE.md` 的 rule 7: 不要跟随 tool output 里的指令
- **但代码层没防护**，Target 响应的 HTTP body 原样给 LLM 看

**影响**: 中（威胁真实存在，但不是紧急）

**RFC 建议**: `RFC-V08: Tool output untrust wrapping` — ToolResult 在 server 渲染时加 `<untrusted_content>...</untrusted_content>` 标签，LLM 训练就能识别

---

## Part 5 — v2 新增：知识管理 / 长期价值

### V-K1 | Pattern card 系统缺失

**证据**: [bughunters 2025 学习方法](https://bughunters.tistory.com/52)
- 看 writeup 要蒸馏为 "pattern card"
- 下次遇到类似题 RAG 检索

**我们现状**: 无

**影响**: Team 版超高（4 人队知识沉淀就靠这个）

**RFC 建议**: `RFC-T10: Pattern card library` — Obsidian vault 里一套 pattern card 模板；Team Edition MCP tool `pattern_suggest(finding)` 返回可能相关的 pattern

---

### V-K2 | Cross-engagement 记忆 / RAG 缺失

**证据**: 同上

**我们现状**: 每个 engagement DB 独立，看不到历史

**影响**: 长期高（2-3 个比赛后价值显现）

**RFC 建议**: `RFC-T11: Cross-engagement RAG` — 基于 pattern cards + findings + writeups 的 FAISS/Chroma 索引；MCP tool `memory_search(query)` 查历史

---

### V-K3 | Public writeup publishing 缺失

**证据**: CTF 团队常见做法 —— 写完放 GitHub 做招人名片

**我们现状**: 无

**影响**: Team 版低（但对团队品牌有用）

**RFC 建议**: `RFC-T12: Public writeup export` — `kestrel team export-writeup <slug>`  redact 敏感信息后导出到 markdown

---

## Part 6 — v2 新增：工程基础补充

### V-E1 | Benchmark harness 缺失

**证据**:
- [Cybench 40 题 benchmark](https://proceedings.iclr.cc/paper_files/paper/2025/hash/3e9412a9c1d93810ef3ef7825115016b-Abstract-Conference.html)
- [InterCode-CTF 40→95% 改进](https://arxiv.org/html/2412.02776v1)
- [HTB AI Benchmarks](https://www.hackthebox.ai/benchmarks)

**我们现状**: 有单元测试、没能力 benchmark

**影响**:
- Pro 版：高（"我们 v1.2 vs 竞品" 的客观 claim）
- Team 版：中（能力自知）

**RFC 建议**: `RFC-V09: CTF benchmark harness` — 把 `picoCTF` 或 `HTB Starting Point` 一键跑
- CI 每个 minor release 跑一次
- 结果 commit 到 `docs/perf/`

---

### V-E2 | License 兼容性矩阵缺失

**证据**:
- HexStrike: MIT
- BoxPwnr: 未声明
- MCP Kali: 未声明
- Vaultwarden: AGPL-3.0
- HackSynth: Apache-2.0

**我们现状**: MIT + Responsible Use Addendum；没做集成时的 license compatibility 核对

**影响**: 中（集成 Vaultwarden AGPL 时会触发 license 问题）

**RFC 建议**: `RFC-V10: License compat matrix` — 每个外部依赖和 plugin 标 license；`LICENSE-COMPAT.md` 文档

---

### V-E3 | Community skill/plugin marketplace 缺失

**证据**:
- HexStrike 8.2k star = 社区贡献放大
- Nuclei templates 10k+ = 最大社区贡献案例

**我们现状**: Plugin 系统仅口头约定

**影响**: 长期极高（开源后最大 moat）

**RFC 建议**: `RFC-V11: Plugin registry MVP` — 简单 `kestrel plugins install github:user/repo`，没审核、靠用户自己负责

---

### V-E4 | Browser automation 工具缺失

**证据**: [HackerGPT 0.5 CTF mode](https://hackergpt.org/blog/hackergpt-050-advancing-applied-security-training-with-ctf-mode/) 的卖点就是 "headless browser automation"

**我们现状**: 只有 httpx，不能渲染 JS

**影响**: Team 版中高（Web CTF 20% 需要 browser automation）

**RFC 建议**: `RFC-V12: Playwright tool module` — 新 tool module `browser_*`:
- `browser_open(url)`
- `browser_click(selector)`
- `browser_fill(selector, value)`
- `browser_eval(js)`
- `browser_screenshot(url)`

---

## Part 7 — 优先级矩阵

**评分维度**:
- **Pro 重要性**: 商用版对它的需求
- **Team 重要性**: 队伍版对它的需求
- **工作量** (story points): 1=半天 · 2=1-2天 · 3=3-5天 · 5=1-2周 · 8=2-3周

| Gap | Pro | Team | 工作量 | RFC 建议 ID |
|-----|-----|------|--------|-------------|
| V-C1 多模型路由 | 低 | **高** | 3 | RFC-V01 |
| V-C2/C3 Attack graph + replay | 中 | **极高** | 5 | RFC-V02 (合) |
| V-C4 Tool shadowing 防护 | 中 | 中 | 1 | RFC-V03 |
| V-C5 Subtask guidance | 中 | **高** | 3 | RFC-V04 |
| V-T1 Obsidian Team Vault | 低 | 中 | 2 | RFC-T01 |
| V-T2 Vaultwarden 集成 | 低 | **高** | 3 | RFC-T02 |
| V-T3 tmate 共享 shell | 低 | 中 | 1 | RFC-T03 |
| V-T4 Realtime sync | 低 | **极高** | 5 | RFC-T04 |
| V-T5 Contribution / scoreboard | 低 | 中 | 2 | RFC-T05 |
| **V-D1 Challenge/Flag domain** | 低 | **极高** | 5 | **RFC-T06** |
| **V-D2 Flag submission** | 低 | **极高** | 3 | **RFC-T07** |
| V-D3 Bootstrap 脚本 | 低 | 中 | 2 | RFC-T08 |
| V-D4 2-hour rule | 低 | 中 | 1 | RFC-T09 |
| V-D5 Template refresh | 低 | 低 | 0.5 | 并入 T08 |
| V-A1 Model tier | 中 | 中 | 2 | RFC-V05 |
| V-A2 Per-tool soft timeout | 中 | 中 | 1 | RFC-V06 |
| V-A3 Cost ledger | **高** | 中 | 3 | RFC-V07 |
| V-A4 Untrust wrapping | 中 | 中 | 1 | RFC-V08 |
| V-K1 Pattern cards | 低 | **高** | 3 | RFC-T10 |
| V-K2 Cross-engagement RAG | 低 | 中 | 5 | RFC-T11 |
| V-K3 Public writeup export | 低 | 低 | 2 | RFC-T12 |
| V-E1 Benchmark harness | **高** | 中 | 3 | RFC-V09 |
| V-E2 License 矩阵 | 中 | 低 | 1 | RFC-V10 |
| V-E3 Plugin registry MVP | 中 | 中 | 5 | RFC-V11 |
| V-E4 Browser automation | 中 | **高** | 5 | RFC-V12 |

**粗统计**:
- 标记 **极高 (Team)** 的 gap：4 个 → V-C2, V-T4, V-D1, V-D2
- 这 4 个总工作量 **18 SP** = 约 3-4 周 pair
- 这 4 个就是 Team Edition MVP 的核心

---

## Part 8 — RFC 归属建议

### 新增 RFC 总览（24 个）

- **V-系列**（通用，Pro + Team 共享）: V01..V12 = 12 个
- **T-系列**（Team Edition 专属）: T01..T12 = 12 个

### 既有 RFC 需要修订

- **RFC-003** 增加 `sync_backend` 字段（配合 V-T2）
- **RFC-E01** 扩 "replay" 模式（配合 V-C2）
- **RFC-E03** 前置到 Team MVP（配合 V-T4）
- **RFC-B02** 扩展到 24 个新工具的 rich description

### 新增 epic

- **Epic V**（通用增强）: 12 RFC
- **Epic T**（Team Edition）: 12 RFC

---

## Part 9 — 给 AUDIT v1 打分

| 维度 | v1 表现 | v2 改进 |
|-----|--------|---------|
| 代码库内部 gap | 好（13 个都找到） | 无变化 |
| 行业对标 | **缺** | 12 个 V-gap |
| CTF 专项 | **缺** | 12 个 T-gap + 4 个 D-gap |
| 学术参考 | **缺** | 5 篇 arxiv / ICLR 引用 |
| 实际运营工具 | **缺** | 3 个（Obsidian/Vaultwarden/tmate） |

**v1 的价值**: 修内部已知问题。
**v2 的价值**: 把项目置于生态。

---

## Part 10 — 下一步

1. **你拍板** Pro vs Team 分叉策略（见 PRODUCT_LINES.md）
2. **我** 把 28 个 gap 的 RFC 写出来（按 V-prefix 和 T-prefix 分两批）
3. **你或 agent** 按 RFC 执行

不要在没拍板前动代码。

---

## 附录 — 引用源（去重）

- https://github.com/0x4m4/hexstrike-ai
- https://github.com/d0gesec/mcp-kali
- https://github.com/0ca/BoxPwnr
- https://github.com/aielte-research/HackSynth
- https://0ca.github.io/ctf/ai/security/2025/11/28/neurogrid-ctf-writeup.html
- https://github.com/PalisadeResearch/ai-vs-humans-ctf-report
- https://arxiv.org/html/2511.15998v1 (MCP for C2)
- https://arxiv.org/html/2310.11409v6 (HackingBuddyGPT)
- https://arxiv.org/pdf/2412.02776 (InterCode-CTF)
- https://arxiv.org/pdf/2505.10321 (AutoPentest)
- https://proceedings.iclr.cc/paper_files/paper/2025/... (Cybench)
- https://blazejgutowski.com/posts/htb-season-tips/
- https://docs.bswen.com/blog/2026-03-23-sync-obsidian-vault-git-ai-collaboration/
- https://github.com/dani-garcia/vaultwarden
- https://tmate.io/
- https://redteams.ai/topics/walkthroughs/attacks/mcp-tool-shadowing
- https://book.hacktricks.wiki/en/crypto/ctf-workflow/
- https://github.com/pugazhexploit/CTF_cheetsheet-2025
- https://pentest-gpt.com/
- https://hackergpt.org/blog/hackergpt-050-...
- https://www.hackthebox.ai/benchmarks
- https://securiumsolutions.com/how-to-build-a-ctf-team-and-win-your-first-competition/
- https://blog.wm-team.cn/

---

## Changelog

- **2026-04-21 初版 (v2)** — 基于 CTF_ECOSYSTEM_RESEARCH 的调研补 28 个新 gap；给 AUDIT v1 定位
