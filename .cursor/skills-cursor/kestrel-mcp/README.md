# Kestrel-MCP Skills

Cursor skills for the Kestrel-MCP (`d:\TG PROJECT\kestrel-mcp`) project.

## Install

```powershell
.\scripts\install_skills.ps1           # symlink (recommended, needs admin or dev mode)
.\scripts\install_skills.ps1 -Mode copy  # fallback copy
.\scripts\install_skills.ps1 -Uninstall  # remove
```

Restart Cursor after install.

## Skill tree

```
kestrel-mcp/
├── SKILL.md                          Root — always loaded, routes to sub-skills
├── bootstrap/                        New agent onboarding
├── exec/
│   ├── rfc/                          Execute ONE RFC (single, sequential)
│   ├── rfc-chain/                    Execute MULTIPLE RFCs in sequence (DAG order)
│   └── rfc-parallel/                 Execute INDEPENDENT RFCs in worktrees
├── plan/                             Author new RFC or split over-budget RFC
├── audit/
│   ├── codebase/                     AUDIT_V2-style gap analysis
│   ├── rfc/                          Validate RFC format + executability
│   └── diff/                         PR/diff code review
├── handoff/                          Snapshot state + resume from snapshot
├── query/                            Status / next-step / metrics lookup
├── health/                           verify_state or rollback
├── roles/
│   ├── spec-author/                  Persona: write RFCs for weak models
│   ├── backend-engineer/             Persona: execute RFCs disciplined
│   └── code-reviewer/                Persona: review with evidence
└── team/                             Team Edition ops (bootstrap, session)
```

## Trigger cheat sheet

| You say | Skill activates |
|---------|-----------------|
| "开始工作" / "new session" | `bootstrap/` |
| "run RFC-A04" / "执行 RFC-A04" | `exec/rfc/` |
| "连续跑 A04 T00 T08" | `exec/rfc-chain/` |
| "并行跑这 3 个 RFC" | `exec/rfc-parallel/` |
| "把 X 写成 RFC" | `plan/` |
| "审计代码" / "audit codebase" | `audit/codebase/` |
| "审这份 RFC" | `audit/rfc/` |
| "review 这次改动" | `audit/diff/` |
| "快照" / "交接" / "handoff" | `handoff/` |
| "查 RFC 进度" / "next" | `query/` |
| "健康检查" / "回滚" | `health/` |
| "写 RFC 的思路" | `roles/spec-author/` |
| "code review mode" | `roles/code-reviewer/` |
| "team bootstrap" / "开 ops" | `team/` |

## Design principles

### Why multiple skills instead of one mega-skill?

Each skill is **small and single-purpose** so:
- Weak local models (Qwen-7B) can fit one skill's context + the active file + the RFC
- Cursor's skill matcher picks the right one by trigger words
- Each skill has explicit forbidden behaviors — reduces blast radius

### Why the 3 layers (exec / audit / roles)?

- `exec/` is **verbs** — "do this thing"
- `audit/` is **nouns being inspected** — "check this thing"
- `roles/` is **personas** — "think like this person"

A user can combine: "act as spec-author and plan an RFC" = `roles/spec-author/` +
`plan/` both active.

### Why `team/` is separate?

Team Edition has distinct operational semantics (unleashed mode, crew
coordination). Mixing team-specific flows into core skills would confuse Pro
users. Pro users never trigger `team/` unless they explicitly say "team".

## Contributing

New skill template:

```markdown
---
name: kestrel-mcp-<category>-<name>
description: >
  <one sentence what it does>. Trigger on: "<trigger1>", "<trigger2>", "<中文 1>",
  "<中文 2>". <any constraint, e.g. read-only>.
---

# <Title>

## Decision / Step 1

<what the skill does first>

## Forbidden

<what it must NOT do>
```

Keep each skill **under 200 lines**. Longer = split it.

## Relationship to RFCs

- `AGENT_EXECUTION_PROTOCOL.md` is the **contract**.
- RFCs in `rfcs/` are the **work**.
- Skills in this directory are the **interface** — how agents trigger work.

Skills never contain project business logic. They route to RFC files + protocol.
If a skill would duplicate information from an RFC, reference the RFC instead.
