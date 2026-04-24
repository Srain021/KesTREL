---
name: kestrel-mcp-plan
description: >
  Author new RFCs from a feature request, or split an over-budget RFC. Trigger
  on: "write RFC for X", "把 X 需求写成 RFC", "plan feature X", "split RFC-NNN",
  "拆分 RFC", "propose RFC", "draft RFC for Y".
---

# Plan — author or split RFCs

You are in **Spec Author** mode. See `roles/spec-author/SKILL.md` for persona.

## Decision tree

| User says | Route |
|-----------|-------|
| "write RFC for <feature>" | § New RFC |
| "propose RFC for <gap>" | § New RFC |
| "split RFC-NNN" | § Split existing |
| "拆 RFC-NNN" | § Split existing |
| "RFC-NNN is too big" | § Split existing |

---

## § New RFC

### Step 1 — Clarify

Ask 3-5 clarifying questions max before drafting. Focus on:

- What **GAP** or **USER_STORY** or **AUDIT entry** this addresses (must cite one)
- Which **edition** it targets: `pro`, `team`, or `both`
- Hard **Non-goals** (critical — prevents scope creep)
- Expected **blocking_on** (read `rfcs/INDEX.md` first to know existing RFCs)

Never draft without this info.

### Step 2 — Pick next RFC id

- Epic A/H: numeric (`RFC-006` → next is 013)
- Epic B/C/D/E/F/G: letter-prefixed (`RFC-B01` next is `B07`)
- Epic T (Team): `RFC-T01...T12` (T00/T08 taken)
- Epic V (cross-edition): `RFC-V01...V12`

Check `rfcs/INDEX.md` for latest — never collide.

### Step 3 — Estimate budget

Count expected:
- `max_files_touched`: read files ≤ 10 for a single RFC
- `max_new_files`: ≤ 6
- `max_lines_added`: ≤ 400 (**hard limit for a single RFC**)
- `max_minutes_human`: ≤ 60

If estimate > any limit → **split first** (jump to § Split).

### Step 4 — Draft

Use `rfcs/RFC-000-TEMPLATE.md` as template. Copy to `rfcs/RFC-<id>-<slug>.md`.
Fill in every required front-matter field. No blanks.

For `Steps`: use only WRITE / REPLACE / APPEND / RUN keywords. No prose commands.
Each step atomic. SEARCH blocks in REPLACE must be unique in target file.

### Step 5 — Write verify_cmd

Must be:
- Single PowerShell-compatible line (or multi-line block in `|`)
- Runs only the new tests for this RFC (not full suite — that's `full_verify`)
- Exit 0 = green
- Independent of HEAD state beyond this RFC's changes

Example templates:
```
.venv\Scripts\python.exe -m pytest tests/unit/<module>/ -v
.venv\Scripts\python.exe -m redteam_mcp.__main__ <new-cli-cmd> --help
```

### Step 6 — Write rollback_cmd

Two-part:
- `git checkout -- <each file in files_will_touch>`
- `rm <each new file in files_will_touch>`

Must leave working tree at pre-RFC HEAD state.

### Step 7 — Add Notes for executor

List **gotchas** a weak local model would miss:
- Specific import path quirks
- Windows vs Unix path handling
- Pydantic v2 surprises (frozen, field_validator)
- Typer callback ordering
- SQLAlchemy async lazy-load traps

### Step 8 — Submit for review

Invoke `audit/rfc/` skill on the new RFC. Must pass all checks before it goes
into `rfcs/INDEX.md`.

---

## § Split existing

### Step 1 — Read target

Read the RFC being split. Check:
- Why over budget? (lines > 400? files > 10? time > 60min?)
- Are there natural seams (e.g. "add feature X" + "add tests for X" can split)?

### Step 2 — Propose split

Present 2-3 split options:

```
Option A (2-way split):
  RFC-NNNa: domain + migrations (180 lines)
  RFC-NNNb: UI + tests (220 lines)
  Dependency: NNNb blocks on NNNa

Option B (3-way split):
  ...
```

Wait for user to pick.

### Step 3 — Execute split

For chosen option:
1. Copy original RFC to `rfcs/RFC-<old>-SPLIT-INTO-<newA>-<newB>.md` (history)
2. Mark original `status: abandoned` with reason "split into ..."
3. Write new RFC files following § New RFC steps 2-8

### Step 4 — Update INDEX

Remove original from INDEX's main table, mark abandoned, add new RFCs with
correct `blocking_on`.

### Step 5 — Audit

Run `audit/rfc/` on each new RFC.

---

## Hard rules

- RFC body in Chinese OK; RFC **code** and **front-matter** English only.
- Do not invent RFC ids > 20 ahead of current max.
- Do not draft an RFC that would break an existing one's `verify_cmd`.
- Always cite the source (GAP / USER_STORY / AUDIT entry) in Context section.
