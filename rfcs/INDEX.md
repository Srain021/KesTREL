# RFC INDEX

> 状态权威表。任何 RFC 状态变化必须在此更新。
> Reviewer 合并 PR 时同步此表 + 本 RFC 文件的 `status` 字段。

**Legend**: `open` 未开工 · `in_progress` 进行中 · `blocked` 受阻 · `done` 已合并 · `abandoned` 放弃

---

## 🗺️ 依赖 DAG（简化视图）

```
        ┌── RFC-001 (uv-lock) ──────────┐
        │                                │
        └── RFC-002 (CI)                 │
                │                        │
                ├── RFC-003 (credstore) ─┼── RFC-B01~B06 (Epic B hardening)
                │                        │
                ├── RFC-004 (ratelimit)  │
                │                        │
                └── RFC-005 (path-safe)  │
                                         │
   RFC-006 (fastapi-skel) ◀──────────────┤
        │
        ├── RFC-007 (web-base-layout)
        │       │
        │       ├── RFC-008 (engagement-routes)
        │       │       │
        │       │       └── RFC-009 (finding-routes)
        │       │
        │       ├── RFC-010 (tool-launcher + SSE)
        │       │
        │       └── RFC-011 (settings-page)
        │
        └── RFC-012 (web-auth-basic)

   Epic D (Web Tier 2)  depends on Epic C done
   Epic E (Web Tier 3)  depends on Epic D done
   Epic F (TUI)         can go in parallel with Epic C after RFC-002
   Epic G (Tools)       depends on nothing (parallel)
   Epic H (Release)     depends on A + C done
```

---

## 📋 Status Table

### Epic A — Engineering foundations

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-001 | lock dependencies with uv         | done   |             |       |
| RFC-002 | GitHub Actions CI matrix          | done   | RFC-001     | agent |
| RFC-003 | Credential Store (domain + API)   | blocked ⚠ | RFC-002  |       |
| RFC-004 | Rate limiting decorator           | done   | RFC-002     | agent |
| RFC-005 | Safe path helper + audit          | done   | RFC-002     | agent |
| RFC-A04 | Edition + FeatureFlags infra      | done   |             | agent |

> ⚠ = `reason: spec_failed_preflight` — see [RFC_AUDIT_PREFLIGHT.md](../RFC_AUDIT_PREFLIGHT.md).
> Do not execute. Spec author must rewrite SEARCH blocks against the real
> source files, or split the RFC to fit within budget caps.

### Epic B — Core hardening

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-B01 | Propagate core_errors everywhere  | open   | RFC-002     |       |
| RFC-B02 | Dumb-model guidance for caido/ligolo/sliver/havoc/evilginx | open | |
| RFC-B03 | THREAT_MODEL status tracking      | open   |             |       |
| RFC-B04 | log schema versioning             | open   | RFC-B01     |       |
| RFC-B05 | Subprocess stderr redaction       | open   | RFC-005     |       |
| RFC-B06 | Tool degradation on missing binary| open   |             |       |

### Epic C — Web UI Tier 1

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-006 | FastAPI app skeleton              | done   | RFC-002     | agent |
| RFC-007 | htmx + Tailwind base layout       | done   | RFC-006     | agent |
| RFC-008 | engagement routes + templates     | done   | RFC-007     | agent |
| RFC-009 | findings table + transitions      | done   | RFC-008     | agent |
| RFC-010 | tool launcher + SSE stdout stream | abandoned | RFC-008 | agent |
| RFC-010a | tool launcher backend jobs      | done   | RFC-008     | agent |
| RFC-010b | tool launcher SSE UI            | done   | RFC-010a    | agent |
| RFC-011 | settings page (keys + paths)      | done   | RFC-007     | agent |
| RFC-012 | HTTP Basic auth for shared deploy | done   | RFC-006     | agent |

> ⚠ = direct spec defects (phantom paths / bad SEARCH / budget). Rewrite needed.
> `blocked-dep` = RFC itself is OK but depends on a broken earlier RFC.

### Epic D — Web UI Tier 2

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-D01 | Markdown editor (Milkdown)        | open   | RFC-009     |       |
| RFC-D02 | PDF export via WeasyPrint         | open   | RFC-D01     |       |
| RFC-D03 | Credentials vault UI              | open   | RFC-003     |       |
| RFC-D04 | Audit log viewer                  | open   | RFC-008     |       |

### Epic E — Web UI Tier 3

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-E01 | Cytoscape attack graph            | open   | RFC-008     |       |
| RFC-E02 | Timeline (gantt) view             | open   | RFC-D04     |       |
| RFC-E03 | Event bus + WebSocket push        | open   | RFC-010     |       |

### Epic F — TUI

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-F01 | Textual skeleton + nav            | open   | RFC-002     |       |
| RFC-F02 | Engagement + Finding views        | open   | RFC-F01     |       |
| RFC-F03 | Tool runner via TUI               | open   | RFC-F02     |       |

### Epic G — Tool expansion

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-G01 | subfinder tool                    | done   |             | agent |
| RFC-G02 | httpx probe tool                  | done   | RFC-G01     | agent |
| RFC-G03 | nmap wrapper                      | open   |             |       |
| RFC-G04 | ffuf wrapper                      | open   |             |       |
| RFC-G05 | Metasploit RPC client             | open   | RFC-003     |       |
| RFC-G06 | Impacket scripts (5 key ones)     | open   |             |       |
| RFC-G07 | NetExec wrapper                   | open   | RFC-003     |       |
| RFC-G08 | BloodHound-CE REST client         | open   |             |       |

### Epic H — Release & community

| id      | title                             | status | blocking_on | owner |
|---------|-----------------------------------|--------|-------------|-------|
| RFC-H01 | Rename to kestrel-mcp             | done   | RFC-002     | agent |
| RFC-H02 | PyPI + Docker release pipeline    | open   | RFC-H01,RFC-002 |   |
| RFC-H03 | MkDocs Material site              | open   | RFC-H01     |       |
| RFC-H04 | v1.0 release gate + announcement  | open   | all above   |       |

### Epic T — Team Edition (unleashed, crew-only)

> Per PRODUCT_LINES.md decision 5: CTF-specific domain (Challenge/Flag/Match) is **cut**.
> Team Edition = "unlimited red-team mode for internal crew" built on existing Engagement/Target/Finding.

| id      | title                              | status | blocking_on         | owner |
|---------|------------------------------------|--------|---------------------|-------|
| RFC-T00 | Team unleashed mode                | done   |             | agent |
| RFC-T08 | Team bootstrap command             | done   |             | agent |
| RFC-T01 | Obsidian Team Vault template       | open   | RFC-T08             | later |
| RFC-T02 | Vaultwarden integration            | open   | RFC-003, RFC-T08    | later |
| RFC-T03 | tmate share-shell tool             | open   | RFC-T08             | later |
| RFC-T04 | Realtime engagement sync (PG)      | open   | RFC-T08             | later |
| RFC-T05 | Actor contribution + scoreboard    | open   | RFC-T08             | later |
| RFC-T10 | Pattern card library               | open   | RFC-T01             | later |
| RFC-T11 | Cross-engagement RAG               | open   | RFC-T10             | later |
| RFC-T12 | Public writeup export              | open   | RFC-T08             | later |

**Team MVP = RFC-A04 + RFC-T00 + RFC-T08**. Everything below is nice-to-have, unblocked but deferred.

> RFC-T06 (CTF Challenge/Flag domain) and RFC-T07 (Flag auto-submission) were proposed in AUDIT_V2 but **cut** per PRODUCT_LINES.md decision 5. See AUDIT_V2.md Part 2 §V-D1..D5 for rationale if reconsidering.

### Epic V — Cross-edition enhancements (deferred)

> From AUDIT_V2.md. Not blocking Team MVP. Order by Pro-importance.

| id      | title                              | status | blocking_on | priority |
|---------|------------------------------------|--------|-------------|----------|
| RFC-V01 | Model routing policy               | open   | RFC-A04     | low      |
| RFC-V02 | Attack graph + replay export       | open   | RFC-E01     | medium   |
| RFC-V03 | Tool namespace collision check     | open   | RFC-002     | medium   |
| RFC-V04 | Subtask guidance for tool handlers | open   | RFC-A04     | medium   |
| RFC-V05 | Tool complexity tier               | open   | RFC-A04     | low      |
| RFC-V06 | Tool soft timeout                  | open   | RFC-A04     | medium   |
| RFC-V07 | Cost ledger                        | open   | RFC-A04     | **high** (Pro) |
| RFC-V08 | Untrust wrap tool output           | open   | RFC-A04     | medium   |
| RFC-V09 | CTF benchmark harness (picoCTF)    | open   | RFC-002     | **high** (Pro) |
| RFC-V10 | License compat matrix doc          | open   | —           | low      |
| RFC-V11 | Plugin registry MVP                | open   | RFC-V03     | medium   |
| RFC-V12 | Playwright browser tools           | open   | RFC-002     | medium   |

---

## 🔓 当前可并行执行的 RFC（最上游，无前置依赖）

- **RFC-G01** — subfinder tool（独立，可平行）
- **RFC-G03** — nmap wrapper（独立）
- **RFC-G04** — ffuf wrapper（独立）
- **RFC-G06** — Impacket scripts（独立）
- **RFC-B03** — THREAT_MODEL status tracking（纯文档，独立）
- **RFC-V10** — License compat matrix（纯文档，独立）

弱模型并行安全：上面 7 个可以同时开 7 个 worktree 各做各的，不会冲突。

## 🚀 Team MVP 关键路径（串行）

```
RFC-A04 (FeatureFlags) ─► RFC-T00 (Unleashed) ─► RFC-T08 (Bootstrap)
                                                     │
                                                     └─► Team MVP complete
```

**当前状态**：Team MVP 已完成；RFC-001 + RFC-002 现已补齐 lockfile 和 CI 基线。

---

## 🧾 统计

| Epic | RFC 数 | full-fleshed | 骨架 |
|------|--------|-------------|------|
| A    | 6      | 6           | 0    |
| B    | 6      | 0           | 6    |
| C    | 7      | 7           | 0    |
| D    | 4      | 0           | 4    |
| E    | 3      | 0           | 3    |
| F    | 3      | 0           | 3    |
| G    | 8      | 0           | 8    |
| H    | 4      | 1           | 3    |
| T    | 10     | 2           | 8    |
| V    | 12     | 0           | 12   |
| **Total** | **63** | **15** | **48** |

「full-fleshed」= 可以直接交给 Qwen-7B 执行；「骨架」= 需要先展开才能执行。

---

## 🔁 如何更新这张表

每个 RFC 合并 PR 时，运行：

```
.venv\Scripts\python.exe scripts\sync_rfc_index.py           # 写入
.venv\Scripts\python.exe scripts\sync_rfc_index.py --check   # 仅检查（CI 用）
```

该脚本扫描 `rfcs/RFC-*.md` 的 YAML front-matter 并输出聚合状态表。

**当前行为**：INDEX.md 尚未加 `<!-- BEGIN_RFC_TABLE -->` / `<!-- END_RFC_TABLE -->`
占位标记，所以脚本目前只打印建议结果不改文件。后续 RFC 会在合适的小节位置插入
标记以启用自动替换（避免覆盖本文件已有的 DAG 图和 MVP 关键路径说明）。
