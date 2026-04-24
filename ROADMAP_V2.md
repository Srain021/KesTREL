# Kestrel-MCP v1.0 → v2.0 收口计划

> 目标：在 **6 周 / ~150 小时** 内补齐剩余 40%，从 MVP 进化到完整平台。
> 原则：先修信用（README 不吹牛），再补深度（工具能打仗），最后造生态（Plugin + TUI）。

---

## Phase 1: 信用修复（Week 1，~20h）

**目标：让 README 和代码完全一致，消除过度承诺。**

### 1.1 补齐 README 缺失的工具声明
- [ ] 在 README 工具矩阵中加入已实现但未列出的工具：Subfinder、httpx、Nmap、ffuf、Impacket、BloodHound、Readiness、Engagement
- [ ] 给 Evilginx、Sliver、Havoc、Ligolo 的 README 描述添加 "(limited)" 标注，诚实说明哪些 action 还没实现
- [ ] 在 Workflows 行标注 "recon_target ✅, generate_pentest_report ✅, full_vuln_scan ❌, exploit_chain ❌"

### 1.2 清理 3 个死 Feature Flag
- [ ] `cost_ledger`：**决策点** — 要么在 `call_tool`  dispatch 中写入 `ToolInvocation` 记录并估算成本，要么从 `FeatureFlags` 中移除
- [ ] `tool_soft_timeout_enabled`：**决策点** — 要么在 `executor.py` / `server.py` 中检查 `ToolSpec.soft_timeout_sec` 并设置 asyncio timeout，要么移除字段和标志
- [ ] `untrust_wrap_tool_output`：**决策点** — 要么在 `_render_result()` 中按 flag 包裹 `<untrusted>` 标签，要么移除
- **建议**：全部移除。它们增加了配置复杂度但没有用户明确要求。等真实需求出现再添加。

### 1.3 ToolInvocation 审计表写入
- [ ] 在 `server.py` `call_tool` dispatch 中，调用成功后异步写入 `ToolInvocation` 记录
- [ ] 包含：tool_name、arguments（脱敏）、engagement_id、duration_ms、exit_code、result_size_bytes
- [ ] 让 `finding_list` / `engagement_show` 可以按时间线查询工具调用历史

---

## Phase 2: 工具深度补齐（Week 2-3，~40h）

**目标：让 Phase 2/3 工具从"能启动"变成"能打仗"。**

### 2.1 Evilginx 深度操作
- [ ] `evilginx_enable_phishlet` — 通过写入 `~/.evilginx/config.json` 或直接调用 evilginx 的 API（如果有）启用指定 phishlet
- [ ] `evilginx_create_lure` — 在 enabled phishlet 下生成 lure URL，返回给操作员
- **工作量**：~8h（需要研究 Evilginx 的非交互式配置方式）

### 2.2 Sliver upload/download
- [ ] `sliver_upload_file` / `sliver_download_file` — 包装 `sliver-client` 的 `upload` / `download` 命令
- [ ] 文件大小限制、路径安全检查（ScopeGuard 扩展）
- **工作量**：~6h

### 2.3 Havoc 真实 Demon 生成
- [ ] **决策点**： Havoc 的 REST API 是否已稳定？
  - 如果稳定：实现 `havoc_generate_demon` 调用 REST API
  - 如果不稳定：保留当前 hint-only 行为，但更新 README 明确说明
- [ ] `havoc_execute_task` — 通过 Havoc 的 REST API 在已上线 session 上执行命令
- **工作量**：~10h（取决于 REST API 文档质量）

### 2.4 Ligolo agent/tunnel 管理
- [ ] `ligolo_list_agents` — 解析 `ligolo` 代理的标准输出，返回结构化 agent 列表
- [ ] `ligolo_start_tunnel` / `ligolo_stop_tunnel` — 包装 ligolo 的 tunnel 命令
- **工作量**：~8h（Ligolo 是交互式 CLI，需要 stdin 驱动技巧）

### 2.5 其余工具接入 Domain 持久化
- [ ] Subfinder、httpx、Nmap、ffuf、Impacket、BloodHound 在发现结果后写入 `Target` / `Finding`
- [ ] 复用 Shodan / Nuclei 已有的 `_ingest_*` / `_persist_*` 模式
- **工作量**：~16h（每个工具约 2-3h）

---

## Phase 3: MCP Resources 与 Workflows（Week 4，~30h）

**目标：完成 MCP Phase 4/5 承诺，让 LLM 能浏览模板和 cheatsheet。**

### 3.1 MCP Resources 实现
- [ ] 在 `resources/__init__.py` 实现资源扫描器（类似 prompts 的 .md 文件扫描）
- [ ] 在 `server.py` 注册 `@mcp.list_resources()` 和 `@mcp.read_resource()`
- [ ] 首批资源：
  - `nuclei-template-index` — 已安装模板列表（调用 `nuclei list-templates` 并缓存）
  - `evilginx-phishlet-index` — 可用 phishlet 列表
  - `tool-cheatsheet/{tool_name}` — 每个工具的常用参数速查表
- **工作量**：~12h

### 3.2 Workflows 补齐
- [ ] `full_vuln_scan` — 编排：Subfinder 枚举 → httpx 探测 → Nuclei 全 severity 扫描 → 结果汇总
- [ ] `exploit_chain` — 编排：读取 Finding → CVE 匹配 → EPSS/KEV 查询 → 生成 exploit 建议（不执行）→ 输出攻击路径图
- **工作量**：~18h

---

## Phase 4: Plugin 系统 MVP（Week 5，~40h）

**目标：让第三方可以通过 pip install + entry-points 注册工具，无需改核心代码。**

### 4.1 动态工具发现
- [ ] 在 `tools/__init__.py` 中保留硬编码列表作为 fallback
- [ ] 增加 `pkg_resources.iter_entry_points(group="kestrel_mcp.tools")` 扫描
- [ ] 第三方包只需：`setup(entry_points={"kestrel_mcp.tools": ["mytool = mypkg.tools:MyToolModule"]})`

### 4.2 Plugin 规范
- [ ] 定义 `ToolModule` 的公共 API 契约（哪些方法/属性是必须的）
- [ ] 提供 `kestrel-mcp-plugin-template` cookiecutter 模板仓库
- [ ] 文档：如何开发、测试、发布一个第三方工具插件

### 4.3 内部工具迁移为 Plugin 演示
- [ ] 把 `readiness_tool.py` 或 `subfinder_tool.py` 抽成独立的 `kestrel-mcp-subfinder` 包
- [ ] 验证 entry-point 注册在 CI 中通过
- **工作量**：~40h（含文档和模板）

---

## Phase 5: 发布与生态（Week 6，~20h）

### 5.1 v1.5.0 发布
- [ ] 更新 `pyproject.toml` version → `1.5.0`
- [ ] 更新 `CHANGELOG.md`
- [ ] 打 tag `v1.5.0`，触发 PyPI + GHCR + GitHub Release
- [ ] 验证 Docker 镜像可运行

### 5.2 文档补齐
- [ ] 每个工具一页深度使用指南（放在 `docs/tools/`）
- [ ] 英文版 user manual（对标已有的 `user-manual.zh-CN.md`）
- [ ] Plugin 开发指南

### 5.3 License 升级（可选，视法律意见）
- [ ] MIT → Apache-2.0 + Responsible Use Addendum
- [ ] 或保留 MIT，但增强 `SECURITY.md` 和 `LICENSE` 中的责任条款

---

## 关键决策点

| 决策 | 选项 A | 选项 B | 建议 |
|------|--------|--------|------|
| 死 feature flag | 全部接线实现 | 全部移除 | **移除**（YAGNI） |
| Havoc Demon 生成 | 等上游 REST API | 现在做 CLI 模拟 | **等 REST API**，README 诚实标注 |
| Plugin 系统 | entry-points | 动态文件扫描 | **entry-points**（Python 生态标准） |
| License | 升级 Apache-2.0 | 保留 MIT | **保留 MIT** + 加强责任条款（更易于采用） |
| TUI | Phase 2 做 Textual | 跳过 TUI 直接做 WebUI Tier 2 | **跳过 TUI**，WebUI 更通用 |

---

## 工作量汇总

| Phase | 内容 | 预估工时 | 产出 |
|-------|------|----------|------|
| Phase 1 | 信用修复 | 20h | README 诚实、死 flag 清理、审计可查询 |
| Phase 2 | 工具深度 | 40h | 6 个新工具 action + 8 个工具接入 domain |
| Phase 3 | Resources + Workflows | 30h | MCP Resources 端点 + 2 个 workflow |
| Phase 4 | Plugin MVP | 40h | 动态加载 + 模板 + 文档 |
| Phase 5 | 发布 + 生态 | 20h | v1.5.0 tag、PyPI、文档补齐 |
| **合计** | | **150h** | **约 6 周（每周 25h）** |

---

## 如果只有 2 周时间

砍掉 Phase 4（Plugin）和 Phase 5 文档深度，只做：
- Phase 1（信用修复）
- Phase 2（工具深度）
- Phase 3 的 Workflows 部分

**2 周产出：一个 README 诚实、工具能打、有 recon→report 全链路的可靠平台。**
