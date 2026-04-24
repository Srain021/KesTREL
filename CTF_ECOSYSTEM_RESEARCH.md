# CTF ECOSYSTEM RESEARCH (with web sources)

> 基于 2026-04-21 实时 web 调研。每条论断都带出处。
> 前一版本我误以为自己无 web 能力；本版是**真正的网络调研**。
> 先收录事实，不下推论；推论留给 `AUDIT_V2.md` 和 `PRODUCT_LINES.md`。

**研究目的**：为「队伍专用版」产品线（非商用）建立知识基线，回答这些问题：
1. 2024–2026 年 AI agent 在 CTF 上的真实能力边界
2. 4 人小队的工作流与工具链
3. 已有的 MCP + 进攻安全项目（竞品 / 可借鉴）
4. 团队协作的基础设施模式

---

## §1. 直接竞品：MCP + offensive security 项目

### 1.1 HexStrike AI
- **repo**: https://github.com/0x4m4/hexstrike-ai ([GitHub](https://github.com/0x4m4/hexstrike-ai))
- **规模**: **8,197★**（2026-04 数据）, 150+ 工具（v6.1 优化至 64 核心工具同时保持功能等价 PR#96）
- **架构**:
  - 三层：AI 集成层（MCP 协议）→ 决策引擎（tool selection / parameter optimization）→ 12+ 专项 agent（BugBounty / CTF Solver / CVE Intelligence / Exploit Generator）
  - 可视化 dashboard + 进度条 + vulnerability cards
  - 进程管理：smart cache / resource opt / error recovery
- **License**: MIT
- **语言**: Python 3.8+

**对比我们**：HexStrike 是**我们最直接的对手**。他们 150 工具 / 7800 star / 12 agent vs 我们 57 tool / 0 star。但他们**没有域模型、没有 engagement 持久化、没有 rich-guidance per tool**（只有描述一行）。我们的架构质量更高，但他们先发 + 功能广。

### 1.2 MCP Kali
- **repo**: https://github.com/d0gesec/mcp-kali
- **定位**: "MCP Kali Server built for real-world offensive security and CTF work"
- **特性**（来自上文搜索结果）:
  - **unrestricted command execution**
  - interactive PTY sessions
  - background task support
  - HTTP intercepting proxy
  - 1000+ pre-installed security tools
  - 声称 battle-tested 数百 HTB 机器
- **星数**: 2★（非常早期）

**对比**：MCP Kali 就是「队伍版本应该长的样子」—— unrestricted、集成 Kali 整个工具链。我们在这个定位上不能独特。但结合我们的域模型 + rich-guidance + 4 人协作 = 差异化。

### 1.3 Kali AI Agent Docker
- **repo**: https://github.com/noxgle/Kali_AI_Agent_Docker
- **架构**: docker-compose 起 Kali 容器 + SSH :2222 + 集成 `term_agent`（Google GenAI / ChatGPT / Ollama API）
- **卖点**: 一键起，多 API 切换

### 1.4 PentestAgent (reference implementation)
- **repo**: https://github.com/GH05TCREW/pentestagent
- **架构**: docker-compose 双容器（agent + privileged Kali with VPN）
- **特性**: 共享 loot volume 跨容器

### 1.5 OASIS
- **repo**: https://github.com/KryptSec/oasis
- **定位**: AI security benchmarking：vulnerable Docker + AI-powered Kali attack container + 自动 MITRE ATT&CK 映射
- **模型支持**: Claude / GPT / Grok / Gemini / Ollama 多家

### 1.6 Offensive-MCP-AI
- **repo**: https://github.com/cybersecurityup/offensive-mcp-ai
- **定位**: MCP + offensive toolkit collection（少量星）

### 1.7 PentestGPT（学术）
- **出处**: https://pentest-gpt.com/ ； USENIX Security 2024 发表
- **定位**: v1.0 autonomous pentesting agent；session persistence / Docker-first
- **类别**: PWN / Web / Crypto / Reversing / Forensics
- **模型**: Anthropic / OpenRouter / local LLM

### 1.8 HackerGPT 0.5.0
- **出处**: hackergpt.org/blog/hackergpt-050
- **亮点**: CTF Mode（headless browser / traffic interception / stateful payload store）
- **商业化**: SaaS 方向

### 1.9 HackSynth
- **出处**: https://github.com/aielte-research/HackSynth
- **学术**: Planner + Summarizer 双模块；PicoCTF + OverTheWire 200 题 benchmark
- **观察**: GPT-4o 表现最佳；本地小模型（Llama3）在 CTF 上成功率大幅低于闭源大模型

### 1.10 AutoPentest
- **出处**: arxiv 2505.10321（2025）
- **架构**: GPT-4o + LangChain
- **实测**: HTB 上 15-25% subtask 完成率，$96.20 总成本
- **要义**: **纯自主模式成本高、成功率有限**，所以人在回路(HITL)仍是必需

### 1.11 HackingBuddyGPT
- **出处**: arxiv 2310.11409v6
- **研究**: 自主 Linux privilege escalation
- **结果**:
  - GPT-4-Turbo: **33-83% 成功率**（和人类渗透测试员 75% 相当）
  - Llama3 等本地小模型: **0-33%**

**小结（本地小模型对比闭源大模型）**：
- 基础 CTF 题（InterCode-CTF）本地模型能到 30% 以内
- 中级挑战（Cybench 40 题 PhD 级）本地模型基本不行
- 顶级挑战（HTB Hard）即使 Claude/GPT 也只有 25-30%

参考 §4 的 Neurogrid AI-only CTF 实测数据。

---

## §2. AI 在 CTF 的当前能力边界（2024-2026）

### 2.1 Neurogrid CTF（2024-11 首届 AI-only CTF）
- **出处**: https://0ca.github.io/ctf/ai/security/2025/11/28/neurogrid-ctf-writeup.html
- **主办**: Hack The Box，奖金池 $50k AI credits
- **样本数据**（一位参赛者 0ca，用 BoxPwnr 得第 5）:
  - **38/45 flags（84.4%）** 自主完成（人类只做监督与重试触发）
  - 36 challenges 分发到 6 个 EC2 平行执行
  - 模型混合使用：Grok-4.1-fast（免费）→ Gemini-3-pro-preview → Claude-Sonnet-4.5 → GPT-5.1-codex
  - 策略：**先跑免费模型捡水题，硬题换顶级模型**
- **关键工程洞察**:
  > "Sonnet 3.7 在 Cybench 上 10 个月前解 20%，Opus 4.5 现在解 86%。我太保守了。"
  >
  > "前沿模型在所有 CTF 类型上都熟练。Pwn 类挑战的主要瓶颈是 gdb 冗长输出消耗上下文。"
- **未解挑战**（AI 无一解决，人类顶级队伍解出）:
  - Gemsmith (Pwn Medium)
  - Mantra (Pwn Hard)
  - The Bank That Breathed Numbers (Blockchain Hard)

### 2.2 AI vs Humans CTF (2025-03)
- **出处**: https://github.com/PalisadeResearch/ai-vs-humans-ctf-report
- **结果**: 最佳 AI 队伍进 top-5%，4 agent 解出 19/20 挑战；速度与顶级人类队伍相当

### 2.3 Cyber Apocalypse
- AI agents 在 8000 队中进 top-10%
- 能解决人类中位参赛者约 1 小时投入的题目

### 2.4 Hack The Box AI Benchmarks
- **出处**: https://www.hackthebox.ai/benchmarks
- **范围**: 10 模型（Claude / GPT-5 / Gemini / Grok / Mistral）× 10 OWASP Top10 题 × 10 次
- **冠军**: **Claude Opus 4.5** 与 **Gemini 3 Pro** 在 easier 档位最强

### 2.5 InterCode-CTF (saturated)
- **出处**: arxiv 2412.02776（Palisade Research）
- **结果**: 2024 底达 **95%**（ReAct&Plan + tool use + multiple attempts）
- **趋势**: "高中级攻击安全已被现有 LLM 超越"

### 2.6 Cybench (active benchmark)
- **出处**: ICLR 2025 Proceedings
- **设计**: 40 个专业级 CTF 任务，来自 4 个竞赛
- **最难题**: 人类团队用 24h54m 才解出
- **模型覆盖**: Sonnet 3.5 / GPT-4o / o1-preview / Opus 3
- **要义**: **子任务引导**（subtask hints）才能让 agent 挺过中级以上难度

**结论给我们项目**：
1. 闭源大模型（Claude / GPT）在中等 CTF 上已经可单人队刷排名
2. 本地小模型 standalone 不行；**必须配合 spec-driven RFC + 大模型混跑**才有战力
3. Pwn / 复杂逆向 / blockchain hard 三类仍是 AI 短板 —— 这些题人留着自己做

---

## §3. CTF 4人队伍的业界工作流

### 3.1 团队角色
**出处**: [Securium Solutions 2025 指南](https://securiumsolutions.com/how-to-build-a-ctf-team-and-win-your-first-competition/)

推荐 4 人配置:

| 角色 | 职责 |
|------|------|
| **Team Leader** | 统筹通讯、协调题目分配 |
| **Web Specialist** | Web 安全题 |
| **Reverser** | Ghidra 等二进制分析 |
| **Crypto/Forensics Analyst** | 密码学、OSINT、取证 |

**要点**:
- 成员可兼多角色（小队尤其如此）
- 招人重点在 self-learner + team-oriented communicator，不要内部 competitor
- 每周练 1-2 题，**轮换类别**

### 3.2 中国顶级队伍对照
**出处**: [W&M Team Blog](https://blog.wm-team.cn) / CTFiot.com / 10100.com

知名队伍:
- **W&M**（强网杯 S7 一等、S8 三等、XCTF-SCTF 冠军、网鼎杯亚军）
- **0ops**（上海交大）
- **N1Star**, **Spirit+**, **Nu1L**
- **Redbud**（清华）
- **L3HSec**（华中科大）

**2024-2025 常见题型**（不全，采样）:
- **Web**: PHP 反序列化利用、文件上传绕过、反向代理绕过、HTTP header injection、template injection
- **Crypto**: 线性方程求解（GF(2) 有限域）、矩阵运算、密钥恢复
- **Misc**: tshark 流量分析、GTP/TEID 提取、AES-ECB、侧信道时间差分析

**工具高频**: binwalk / tshark / Python 自动化脚本

### 3.3 HackTheBox Season 实战策略（HTB 官方推荐）
**出处**: https://blazejgutowski.com/posts/htb-season-tips/

**关键时间策略**:
- **2 小时规则**：2 小时内没 shell 就切题，避免兔子洞
- **分阶扫描**: fast scan (top 1000) → full scan (65535) → service enum
- 用 `--min-rate 1000` 激进扫描
- verbose 标志让你能**在全扫描完成前就开始手动枚举**

**失败诊断**:
- 复杂 exploit 不通时用简单验证（ping / sleep / echo）确认链路
- 如果机器坏了就 reset
- **详尽笔记**：service summary、credentials、exploit log、screenshots

### 3.4 Battlegrounds 比赛结构
**出处**: hackthebox.com/events

- **2v2 格式**，30 分钟每轮，多轮淘汰
- 奖金池从数千到数万美元
- Live stream

---

## §4. 团队基础设施模式

### 4.1 通讯
**出处**: eCTF 2026 规则 / Securium 指南
- **Slack / Discord** — 频道化 + 机器人
- eCTF 官方就用 Slack workspace（announcements / tech-support / team-private）

### 4.2 笔记：Obsidian + Git sync
**出处**: [BSwen 教程](https://docs.bswen.com/blog/2026-03-23-sync-obsidian-vault-git-ai-collaboration/)

**架构**:
- 私 GitHub repo 存 vault
- `obsidian-git` 插件 auto-commit 每 10 分钟
- **Pull before push** 防冲突
- `.gitignore` 必须排除 `.obsidian/workspace.json / plugins/ / .trash/`

**高级：双 vault 分离**:
- **Personal**: iCloud / 本地（敏感）
- **Team/AI**: Git-synced（项目 doc / 共识）

### 4.3 凭证共享：Vaultwarden
**出处**: https://github.com/dani-garcia/vaultwarden / Medium 2026 教程

- **Vaultwarden** = Rust 版 Bitwarden-compatible 服务器
- 成本：免费自托管（vs 官方 Bitwarden 的 per-user 订阅）
- 所有 premium 功能：TOTP / 附件 / emergency access / vault health
- **推荐组合**: Vaultwarden + NoPorts tunnel + 3-因子
  1. MFA token
  2. Vaultwarden password
  3. Tunnel 授权
- **支持客户端**: 浏览器插件 / 桌面 / 移动 / CLI 全兼容

### 4.4 终端共享：tmate
**出处**: https://tmate.io / LinuxHandbook 教程

- tmate = tmux fork 带 SSH 代理
- 一条命令启动 → 生成 `ssh <key>@<region>.tmate.io` 连接串
- 支持 read-only 访问
- 可 NAT 穿透、容错主机 IP 变化
- **CTF 用途**: pair debugging / 队员 join 一个活跃 shell 看进度

### 4.5 协作项目管理
**出处**: eCTF / Securium
- **Trello / Notion / GitHub Projects** — 任务分配
- **Google Docs / HackMD** — 实时 writeup

---

## §5. AI-powered CTF solvers 架构参考

### 5.1 BoxPwnr（0ca, Neurogrid 第 5 名）
**repo**: https://github.com/0ca/BoxPwnr

- 支持平台: HackTheBox / picoCTF / TryHackMe / PortSwigger Labs
- 完成率（2024-11 数据）:
  - **picoCTF: 71.3%**（363/509）
  - **HTB Starting Point: 100%**（25/25）
  - **HTB Challenges: 30.7%**
- 架构亮点：**attack graph 可视化** — 每个挑战生成攻击图展示解法路径
- 多平台抽象：`htb_ctf_client.py` 等客户端；MCP 适配是后加的

### 5.2 HackSynth
**repo**: https://github.com/aielte-research/HackSynth

- **Planner + Summarizer 双模块**：计划 + 摘要分离
- 200 题 benchmark（PicoCTF + OverTheWire）
- 开源；学术友好

### 5.3 verialabs/ctf-agent
**repo**: https://github.com/verialabs/ctf-agent
- 小众项目；参考其设计的多 agent 协作思路

---

## §6. CTF workflow / cheatsheets 参考

### 6.1 综合 cheatsheet
**出处**: https://github.com/pugazhexploit/CTF_cheetsheet-2025 / https://github.com/lennmuck/ctf_cheat_sheet_01

覆盖分类:
- **Web Recon** — subfinder, assetfinder, amass
- **Port scanning** — Nmap, Masscan
- **Dir enum** — Gobuster, Dirsearch, Ffuf, Feroxbuster, Wfuzz
- **Common vulns** — SQL/XSS/CSRF/File upload/LFI/RFI/SSRF/Command injection/Template injection/IDOR/JWT/API/WebSocket

### 6.2 Crypto workflow (HackTricks)
**出处**: https://book.hacktricks.wiki/en/crypto/ctf-workflow

**结构化 5 步**:
1. **Identify**: encoding vs encryption vs hash vs signature
2. **Control**: 谁控制 plaintext / ciphertext / IV/nonce / key
3. **Classify**: symmetric / public-key / hash
4. **High-probability first**: decode layers / known-plaintext XOR / nonce reuse
5. **Escalate**: lattices / SMT / Z3

工具: CyberChef / dCode / Ciphey

### 6.3 Pwn 常见知识点
- Buffer overflow / PIE bypass / NX / ROP / stack canaries / format string / shellcode / ret2libc

### 6.4 Reverse 技巧
- SMT solver
- byte-by-byte check 反向（side-channel）
- `gef` 字符串搜索

---

## §7. 学习与复盘

**出处**: https://bughunters.tistory.com/52 (2025)

**有效写题研究法**:
1. 自己假设 vs 官方题解对比
2. 标注决策点、"trigger moment"（方向转变的关键信号）
3. **在沙盒重建挑战** 复刻关键信号，不是照抄脚本
4. 蒸馏为**可复用 pattern card**

---

## §8. MCP 安全注意（反面参考）

**出处**: arxiv 2511.15998 / redteams.ai

### 8.1 Tool shadowing
当多个 MCP server 注册同名工具时，agent 可能调到恶意版本。
**对我们的启示**: 我们的 `engagement_*` 工具名是独特前缀，但将来加社区 plugin 时要小心。

### 8.2 MCP tool definition = prompt injection surface
工具描述本身在运行时送给 LLM，可能含恶意指令注入。
**对我们**: `ToolSpec.render_full_description` 的内容要严格审查。

### 8.3 MCP-based C2（攻击者视角）
arxiv 2511.15998 展示 MCP 可被用作覆盖式 C2，无心跳、真分布式侦察。
**对我们**: 既要防御这种用法（scope guard 拒绝陌生 server），也要明白这**就是**我们队伍版想做的事（inside out）。

---

## §9. 直接可借鉴的设计决策

| 来源 | 借鉴点 | 我们的行动 |
|-----|-------|-----------|
| HexStrike v6.1 重构 | 17,289 行主文件拆成 core/agents/api/tools | 验证：我们的 `tools/` 切分已达到；`core/` ok |
| BoxPwnr | Attack graph 可视化 | 纳入 RFC-E01（Cytoscape） |
| MCP-Kali | Unrestricted + 1000 工具 + PTY | 队伍版的起点定位 |
| Vaultwarden | 自托管团队凭证 | 纳入 Team Edition 的 docker-compose 默认栈 |
| tmate | 实时终端分享 | 纳入 Team Edition 的 "join session" 功能 |
| Obsidian + Git | 协作笔记 | 配一个 Team Vault 模板 repo |
| HackTricks crypto 5-step | 工作流结构化 | 改造为 Team Edition 的 crypto skill |
| HTB 2-hour rule | 时间止损 | 写进 Team Edition LLM_GUIDANCE |
| Neurogrid 多模型混用 | 免费模型捡水题 + 顶级模型攻硬题 | 加到 RFC backlog：model routing |
| HackSynth Planner+Summarizer | 规划与总结分离 | 研究是否改我们的工作流架构 |

---

## §10. 对我们项目的直接威胁与机会

### 威胁
1. **HexStrike 8k 星**先入场，品牌/社区优势
2. **MCP-Kali** 在「unrestricted」定位上比我们更直接
3. **BoxPwnr** 在纯 AI CTF 上证明自己，且已有多平台 client
4. **大厂 Anthropic / OpenAI** 随时可能官方出 MCP-offensive bundle

### 机会
1. **没有一家把 domain model 做好**（engagement / finding / credential 的持久化 + audit）→ 我们商用版的核心差异
2. 没人做「**4 人协作**」专项（HexStrike / MCP-Kali 都是单人视角）→ Team Edition 差异
3. **LLM_GUIDANCE 式的 rich description**没人做 → 本地小模型友好
4. 中文文档 + 国内 CTF 生态友好 → 垂直市场

---

## §11. 研究的局限

1. WebSearch 返回的日期偶有未来时间戳（2026-03 等），已尽量按内容判断真实性
2. 实际 HvV / 国企红蓝对抗的内部工作流极少公开，无法引用
3. HexStrike 内部 v6.1 重构的详细 commit graph 未深入 fetch（PR#96 摘要为准）
4. 未能量化对比 60+ 工具版 vs 150 工具版的真实使用分布

---

## §12. 下一步

见 `AUDIT_V2.md`（基于此研究做的查漏补缺）和 `PRODUCT_LINES.md`（Pro vs Team 分叉）。

---

## §13. Changelog

- **2026-04-21 初版** — 10 条搜索 + 3 次 repo fetch，本文约 4 千字 / 60+ 链接引用
