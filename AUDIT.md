# CODEBASE AUDIT

> 写于动工 RFC 之前的诚实盘点。
> 目的不是吹「我们走到哪了」，而是指出**所有不能交给弱模型的地方**，以便 RFC 提前修复。
> 把坏消息写在前面，好消息写在后面。

**Audit date**: 2026-04-21
**Auditor**: pair (human + Claude, no web-search)
**Scope**: everything under `d:\TG PROJECT\redteam-mcp\`

---

## Part 1 — 危险 / 脆弱 / 返工风险

### D-1. 包名 `redteam_mcp` 与未来品牌 `kestrel-mcp` 错位

- `pyproject.toml` 里 package=`redteam_mcp`，CLI=`redteam-mcp`
- 多个文档声明未来会重命名为 `kestrel-mcp`
- 如果先发布 v1.0 再改名，会**破坏所有外部依赖**
- **必须在 v1.0 前决策**，不然后期无法挽救

### D-2. Settings 改 env 很脆弱

- `pydantic-settings.SettingsConfigDict(env_nested_delimiter="__")` + 非列表字段从 env 加载要 JSON
- `authorized_scope: Union[list[str], str]` 靠 validator 转换（GAP_ANALYSIS G-E3）
- 换 pydantic-settings 版本/Windows 编码有历史 bug 重现风险
- **测试只覆盖当前版本**，没有锁文件（无 `uv.lock`/`poetry.lock`）

### D-3. 权限安全「双路径」还没收拢

- 旧：`security.ScopeGuard`（内存，从 settings 读）
- 新：`domain.services.ScopeService`（DB）
- `server._check_scope` 按是否有 engagement 分叉
- 弱模型在新 tool 里容易选错路径。**必须写死规则到 RFC 模板**

### D-4. Plugin 系统是口头约定

- `MASTER_PLAN.md` 说 plugin 可以走 `entry_points`，但**没有代码**
- `domain/__init__.py` / `tools/__init__.py` 都是静态 import
- 外部工具扩展需要 fork 主仓库
- **MVP 前可不做，但要进 RFC backlog**

### D-5. Alembic 迁移依赖 tzdata（Windows 踩过）

- `alembic.ini` 里 `timezone = UTC` 被我们注释了（Windows 上 `zoneinfo` 找不到 UTC）
- 未来切回 Linux CI 要记得取消注释或者装 `tzdata`
- **写进 RFC-002 的 CI workflow 里**

### D-6. Nuclei 解析器脆弱

- `nuclei_tool._parse_jsonl` 假设每行是完整 JSON
- Nuclei JSON 字段偶尔会变（上游版本差异）
- 没有 schema pinning
- 上游升级时必然 breaking，但**没测试捕捉**

### D-7. Subprocess 输出解析（Sliver 表格解析）

- `sliver_tool._parse_table` 用正则定位列位置
- Sliver CLI 输出格式非稳定契约
- 升级 Sliver 大概率要改代码
- **每次集成新 tool 前必须做升级兼容测试**

### D-8. 没有 CI

- 目前所有验证在本机跑
- 没有 `.github/workflows/*`
- 没有矩阵测试（Linux/macOS/Win × Python 3.10/11/12）
- PR review 依赖人眼 + 本地 `full_verify.py`
- **RFC-002 第一个必须做**

### D-9. Secrets 明文

- Shodan API Key 现在在 `~/.cursor/mcp.json` 明文
- 未来 engagement 的 credentials 走 `CredentialStore`，但那个还是 TODO
- **THREAT_MODEL T-I1/T-I6 都指出过，但还没修**

### D-10. 没有持续交付

- 没发布到 PyPI / Docker / GHCR
- 没有版本号以外的 release 机制
- 没有 changelog 自动生成
- **公开发布前必须补**

### D-11. 文档是 Markdown 集合，不是站点

- `MASTER_PLAN.md`、`GAP_ANALYSIS.md` 等是手写 md，互相链接靠相对路径
- 用户在 Cursor 里打开要翻好几层
- **MkDocs/Docusaurus 站点没搭**

### D-12. 「Dumb model 友好」只在 shodan/nuclei 的 ToolSpec 里做了

- 另外 5 个工具模块（caido/ligolo/sliver/havoc/evilginx）用的还是老 description（一句话）
- 新的 `engagement_tool.py` 16 个 spec 也只有部分填了 `when_to_use`、`pitfalls`
- **每个 tool 的 rich guidance 必须进 RFC 清单**

### D-13. 没有 threat-model tracking

- `THREAT_MODEL.md` 列了 30+ 威胁，但没有状态
- 不知道哪些威胁已经修复、哪些还开着
- **RFC 每关闭一个 threat，要在 THREAT_MODEL.md 里更新 status**

---

## Part 2 — 稳定部分（不用再动的）

1. **domain/ 层** 40 个测试覆盖，状态机完善，services 与 storage 分离
2. **core/context.py + ServiceContainer** 10 个测试覆盖，正确处理 async 并发
3. **Shodan 和 Nuclei 的 ToolSpec 描述** 已经是「dumb-model-ready」格式，作为其他工具的模板
4. **full_verify.py** 8 个检查端到端打通，新 RFC 只需要维持 8/8
5. **Alembic schema** 已经有 initial migration，schema 扩展走 `alembic revision --autogenerate`
6. **MCP server 的 dispatch 路径** 已经支持 per-call engagement 注入（`arguments["_engagement"]`）

---

## Part 3 — 弱模型最容易踩的坑（写进 RFC 模板的硬约束）

| # | 陷阱 | RFC 约束 |
|---|------|---------|
| 1 | 在 `core/` 里 import `tools/` | RFC 必须声明「禁止反向 import」 |
| 2 | 把新实体 `session_factory` 直接挂到旧 ScopeGuard | RFC 必须声明「新 tool 一律走 RequestContext」 |
| 3 | 改了 `entities.py` 但忘了同步 `storage.py` | RFC 必须标注「若改实体字段，同步 ORM + migration」 |
| 4 | `alembic revision` 没设 `KESTREL_DB_URL` 生成空 migration | RFC 必须提供完整命令 |
| 5 | 新工具 ToolSpec 的 `dangerous=True` 忘了加 `requires_scope_field` | RFC 的工具模板强制 |
| 6 | 测试里误用 `pytest.mark.asyncio`（已经是 auto-mode） | RFC 测试模板不带 marker |
| 7 | `render_full_description()` 需要至少填 `when_to_use` 和 `pitfalls` | RFC 检查项 |
| 8 | 在 PowerShell 上用 `/tmp` 路径 | RFC 的验证命令用 `pathlib` 或跨平台 |
| 9 | 新增依赖没加到 `pyproject.toml` | RFC 步骤里强制 `uv add` / `pip install` + `pyproject.toml` 同步 |
| 10 | 改了 full_verify 以外的验证 | RFC 必须在最后一步跑 `full_verify.py` |

---

## Part 4 — 可投入资本（已有的资产，新 RFC 可免费用）

1. `ServiceContainer.in_memory()` — 任何测试 fixture 直接用
2. `EngagementService.create()` / `ScopeService.add_entry()` — 测试里 seed 数据
3. `scripts/full_verify.py` — 每个 RFC 结束都跑这个
4. `ToolSpec.render_full_description()` — 新 tool 只要填 dataclass 字段就自动有 LLM 友好描述
5. `core.context.bind_context()` — 手写测试里也能绑 context

---

## Part 5 — 结论：RFC 总量预估

基于 Part 1 的问题 + MASTER_PLAN 的 Sprint 4-7 + GAP_ANALYSIS 的 P0/P1：

- **Epic A 工程地基**: ~5 RFC（D-1, D-2, D-5, D-8, D-10）
- **Epic B 核心加固**: ~6 RFC（D-9, D-12, D-13, 其他 P0）
- **Epic C Web UI Tier 1**: ~7 RFC（Sprint 4）
- **Epic D Web UI Tier 2**: ~4 RFC（Sprint 6）
- **Epic E Web UI Tier 3 + Realtime**: ~3 RFC（Sprint 7）
- **Epic F TUI**: ~3 RFC（Sprint 5）
- **Epic G 工具扩展**: ~8 RFC（纳入 TOOLS_MATRIX 的 Tier 1）
- **Epic H 发布**: ~4 RFC（D-10, D-11 + 公告）

**总计 ~40 RFC**。其中前 12 个（Epic A + C）要「全细粒度」写完，后 28 个可「骨架」够用。

---

## Part 6 — 下一步

见 [AGENT_RESEARCH.md](./AGENT_RESEARCH.md) 和 [AGENT_EXECUTION_PROTOCOL.md](./AGENT_EXECUTION_PROTOCOL.md)。
