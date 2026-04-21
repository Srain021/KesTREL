---
name: kestrel-mcp
description: >
  Root skill for the Kestrel-MCP / kestrel-mcp project (d:\TG PROJECT\kestrel-mcp).
  Always load when the user works in this repo. Routes agent to specialized
  sub-skills: bootstrap, exec (rfc), plan, audit, handoff, query, health, roles, team.
  Trigger on: "kestrel", "kestrel-mcp", any RFC number, "run RFC-*", "audit",
  "next step", "交接", "审计", "执行 RFC".
---

# Kestrel-MCP — Root Skill

You are working on **Kestrel-MCP** (project root: `d:\TG PROJECT\kestrel-mcp`).

## Project facts (memorize)

- **Stack**: Python 3.12, Pydantic v2, SQLAlchemy 2.0 async, FastAPI, Typer, pytest
- **Package name**: `kestrel_mcp` (being renamed → `kestrel_mcp` via RFC-H01)
- **Editions**: `pro` (strict, default) and `team` (unleashed). See `PRODUCT_LINES.md`.
- **Protocol**: Every change goes through an RFC. See `AGENT_EXECUTION_PROTOCOL.md`.
- **Authoritative docs**:
  - `README_FOR_AGENT.md` — agent entry point
  - `AGENT_EXECUTION_PROTOCOL.md` — execution contract
  - `AUDIT.md` + `AUDIT_V2.md` — known gaps
  - `PRODUCT_LINES.md` — Pro/Team strategy
  - `rfcs/INDEX.md` — RFC status table
  - `CTF_ECOSYSTEM_RESEARCH.md` — external research

## Skill tree (you can route to)

| Intent | Skill |
|--------|-------|
| "开始工作" / "new session" / 初次接手 | `bootstrap/` |
| "run RFC-NNN" / "execute" / "做 RFC" | `exec/rfc/` |
| "连续跑 RFC-001..005" | `exec/rfc-chain/` |
| "并行跑多个 RFC" | `exec/rfc-parallel/` |
| "把 X 写成 RFC" / "拆 RFC" | `plan/` |
| "审计代码库" / "查漏补缺" | `audit/codebase/` |
| "审这份 RFC" / "RFC 合规性" | `audit/rfc/` |
| "review 这次 diff" / "PR review" | `audit/diff/` |
| "快照当前进度" / "handoff" / "交接" | `handoff/` |
| "查 RFC 进度" / "next step" / "威胁模型" | `query/` |
| "验证健康" / "回滚" / "full_verify" | `health/` |
| "写 RFC 的思路" (persona) | `roles/spec-author/` |
| "我来实现 RFC" (persona) | `roles/backend-engineer/` |
| "code review" (persona) | `roles/code-reviewer/` |

## Hard rules (never break)

1. **No freestyle file access**. Read only what the triggered skill tells you to read.
2. **No freestyle dependency install**. All deps go through `pyproject.toml` → RFC-001 lock.
3. **No `pip install`, `curl`, `wget`, `find`, `Get-ChildItem -Recurse`** during RFC execution.
4. **No scope creep**. If the task exceeds the active RFC's `files_will_touch`, stop and report.
5. **Evidence > assertions**. Never claim "done" without running `verify_cmd` and showing its output.
6. **Respect `edition`**. If user says "team mode", prefer `--edition team`; never mix Pro/Team behavior silently.
7. **One RFC at a time**. No bundling multiple RFCs into one commit.

## Default posture

Unless the user directs otherwise, start with the `query/` skill (show what's in progress) then ask "what do you want to do next?" — don't jump into edits blindly.
