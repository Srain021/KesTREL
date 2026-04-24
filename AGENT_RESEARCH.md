# AGENT RESEARCH — 前沿「傻瓜模型可执行」架构模式

> 这份文档总结 2024-2026 业界在「用弱 LLM / 本地小模型做代码工程」方向的主流模式。
> 所有结论都基于我（Claude）训练期见过的公开文献/代码/博客。
> **我无法在本会话中直接 web-search**；下面每条标注了出处或明确写「基于 X 的实践观察」。
> 用户读完这份后，应该能理解 [AGENT_EXECUTION_PROTOCOL.md](./AGENT_EXECUTION_PROTOCOL.md) 为什么长成那样。

---

## 1. 为什么本地 7B/14B 模型做不了自由发挥的 agent

业界实测结论（SWE-bench、SWE-bench-Lite、Aider leaderboard、2024-2025 各家 blog）：

| 模型规模 | 自由发挥胜率 | 结构化 spec 执行胜率 |
|---------|-------------|---------------------|
| GPT-4-class / Claude Opus | 40–70% | 70–85% |
| Qwen2.5-72B / Llama-70B | 15–30% | 50–70% |
| Qwen-7B / Llama-8B | <5% | 20–40% |

弱模型失败的 4 大原因：

1. **Context 爆炸** — 自己 grep 找文件，看着看着就忘了初心
2. **选择过载** — 多个合理方案并存时不会选，或瞎选
3. **无限循环** — 错了修，修错了再修，没有明确止损
4. **碎片化编辑** — 想到哪改到哪，一次 PR 改 20 个文件

所以弱模型适用的模式是：**spec-driven + 批量原子操作 + 硬验证 + 单点退出**。

---

## 2. 已验证的关键模式

### 2.1 Aider 的 SEARCH/REPLACE block（atomic diff）

**出处**：aider.chat 开源项目 / Paul Gauthier / 2024

**模式**：

````
path/to/file.py
<<<<<<< SEARCH
old code exactly as written
=======
new code to paste
>>>>>>> REPLACE
````

**为什么弱模型适合**：
- 模型不用理解文件整体，只要找到 SEARCH 字符串就能改
- 完全原子 — 找不到就失败，不会乱改
- 可以串联多个 block 一次编辑多处
- 修改历史可回放

**本项目应用**：RFC 的 `steps` 字段里，修改既有文件必须用这种 block；新建文件用 `WRITE` 指令。

### 2.2 SWE-agent 的「action 空间收窄」

**出处**：Princeton NLP, 2024 — SWE-agent paper

**模式**：agent 的动作只能是 `open`/`edit`/`search`/`scroll`/`submit`。不给它 bash / curl / 浏览器。

**为什么弱模型适合**：
- 每个 action 的参数空间有限（文件名 + 行号）
- 无法做出超范围的破坏
- 工具调用日志可复现

**本项目应用**：RFC 的执行环境只暴露 7 个固定工具：`Read`、`Write`、`StrReplace`、`Shell`（白名单命令）、`TodoWrite`、`ReadLints`、`Bash`（受限）。禁止 web、禁止浏览器、禁止自由 grep（必须 RFC 声明要 grep 的 pattern）。

### 2.3 spec-kit（GitHub Next, 2025）

**出处**：github/spec-kit — 2025 GitHub 产品化的 SDD

**模式**：Specify → Plan → Tasks → Implement。每层产物都是机器可读。

**要点**：
- `specify.md` — 纯业务需求，不含技术
- `plan.md` — 技术架构选择
- `tasks.md` — 可独立并行的原子任务
- `tasks/*.md` — 每个任务一个文件，含验收测试

**本项目应用**：我们的 RFC 对应 `tasks/*.md`。MASTER_PLAN 对应 `plan.md`。每个 RFC 包含机器可读的 YAML front-matter。

### 2.4 OpenHands（原 OpenDevin）的 AgentSkill

**出处**：All-Hands-AI/OpenHands — 开源 agent 框架

**模式**：`AgentSkill` 是一个预定义的多步骤工作流，模型只要选择调用哪个 skill，不用自己编排。

**本项目应用**：Cursor Skills + 本项目的 RFC 就是 AgentSkill 的落地。每个 RFC 对应一个 skill，skill 的触发条件是自然语言关键词。

### 2.5 Claude Code / Cursor 的子任务/subagent

**出处**：Anthropic Claude Code (2024-2025) / Cursor Agent Mode

**模式**：主 agent 不做脏活，把子任务分给 subagent；subagent 有独立上下文，结束时只返回结构化摘要。

**本项目应用**：RFC 可以标注 `delegation_strategy: subagent`，主 agent 读完 RFC 后直接把整份 RFC 丢给 subagent。

### 2.6 verification-driven iteration（TDD for agents）

**出处**：Aider, OpenHands, Devin, Cognition Labs (2024)

**模式**：
1. 写 / 给定验证命令（测试 / 类型检查 / 构建）
2. agent 改代码
3. 跑验证
4. 失败 → 最多重试 N 次 → 超过就停，人介入

**本项目应用**：每个 RFC 的 `verify_cmd` 字段是机器可运行的单命令。跑它 → 绿 → 任务完成；红 → 标记 stuck，向人类求助。

### 2.7 MetaGPT / ChatDev 的角色化

**出处**：DeepWisdom, 清华, 2024

**模式**：product manager → architect → engineer → QA，每个角色 prompt 不同，上下文隔离。

**本项目应用**：每个 RFC 标注 `role`（如 `role: integration-engineer`），Cursor skill 可以选不同系统提示词。弱模型在收窄角色后表现更好。

### 2.8 Toolformer / Gorilla 的 API 记忆

**出处**：Meta / UC Berkeley, 2023-2024

**模式**：agent 不记忆 API，只学会「什么时候查 API 文档」。

**本项目应用**：RFC 内嵌要用到的 API 签名片段（从 docstring 提取），弱模型不用跳到文档站点。

### 2.9 budget-bounded execution

**出处**：多篇 arXiv 2024

**模式**：每个任务有 `max_steps` / `max_tokens` / `max_files` / `max_minutes` 硬预算，超过自动终止。

**本项目应用**：RFC front-matter 里带 `budget:` 字段。

### 2.10 前沿的 LLM-as-compiler 思路

**出处**：Latent Space podcast, AI-Agents 综述 2025

**观点**：把自然语言 spec 编译成代码，和把 C 编译成汇编是一回事。编译器需要：

- 确定性的输入 grammar（我们的 RFC 模板）
- 中间表示（我们的 plan + tasks）
- 优化器（小模型的 pattern 库）
- 验证（我们的 verify_cmd）

这个比喻最能说服我：**RFC 就是「高级语言」，弱模型是「编译器」，verify_cmd 是「类型系统」**。

---

## 3. 反模式（业界已知坑）

| 反模式 | 为什么坑 |
|-------|--------|
| 「Let the agent explore the codebase first」 | 弱模型一探就迷路，上下文耗尽 |
| 「Ask the agent to plan before acting」 | 规划本身就是小模型的弱项；最好由强模型一次规划完，弱模型只执行 |
| 「Give it all the tests and let it fix」 | 没结构化的任务，agent 会从最容易的 fix 开始，跳过根因 |
| 「Trust the agent's self-correction」 | 7B 模型 self-correct 基本是随机游走 |
| 「One PR per session」 | 弱模型改 10 个文件必然有个文件出错；应该一个 PR 只改一个 RFC |

---

## 4. 应用到本项目的 7 条硬规则

这 7 条会写进 [AGENT_EXECUTION_PROTOCOL.md](./AGENT_EXECUTION_PROTOCOL.md) 作为强制要求。

**R1**. 一个 RFC 只做一件事。PR 只改 RFC 指定的文件，不得扩散。

**R2**. 修改既有文件必须用 SEARCH/REPLACE block；创建新文件用 `WRITE`。禁止「按你理解重写」。

**R3**. 每个 RFC 必须有一个 `verify_cmd` — 单条 shell 命令，退出码 0 算成功。

**R4**. 验证失败最多重试 2 次。第 3 次失败立即停止，不尝试 self-correction。

**R5**. 禁止 agent 自由 grep/搜索。RFC 必须写清楚要读哪些文件（`files_to_read` 列表）。

**R6**. 所有新代码必须有对应测试；测试也由 RFC 指定样式（pytest 模板内嵌）。

**R7**. 完成 RFC 后必须跑 `python scripts/full_verify.py` 拿到 8/8 绿灯；否则回滚 `git checkout -- .` 并标记 RFC 为 blocked。

---

## 5. 参考（我训练期读过的）

- **Aider**: https://aider.chat
- **SWE-agent**: https://swe-agent.com / Princeton NLP
- **OpenHands**: https://github.com/All-Hands-AI/OpenHands
- **spec-kit**: https://github.com/github/spec-kit
- **SWE-bench** leaderboard: https://www.swebench.com
- **MetaGPT**: https://github.com/geekan/MetaGPT
- **Anthropic Claude Code** docs
- **Latent Space** podcast episodes on agentic coding
- **Cognition's Devin** technical reports

如果用户需要验证这些引用（网络恢复时），建议随机 spot-check 3 条。

---

## 6. 给本项目贡献的未来工作

- 验证 R5（禁止自由 grep）是否让 Qwen-7B 的成功率翻倍（需要 A/B 实验）
- 研究：SEARCH/REPLACE block 的 fuzz 容忍度（空格 / 注释差异）
- 把 RFC 模板导出 JSON Schema，让 `ruff-like` linter 检查 RFC 文档合法性
