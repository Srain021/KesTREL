---
name: kestrel-mcp-audit-rfc
description: >
  Audit a single RFC for format compliance, executability by a weak model, and
  alignment with AGENT_EXECUTION_PROTOCOL. Trigger on: "review RFC-NNN",
  "audit this RFC", "审查 RFC", "validate RFC", "is RFC-NNN ready". Returns
  pass/fail checklist.
---

# Audit RFC — format + executability

You are a reviewer validating **one** RFC. Read-only.

## Step 1 — Locate RFC

Parse RFC id from user input. Read `rfcs/RFC-<id>-*.md`. If missing, stop.

## Step 2 — Front-matter checklist

Validate YAML front-matter. Each must pass:

```
[ ] id matches filename pattern RFC-<id>-*
[ ] title present, ≤ 80 chars
[ ] epic is one of: A-Foundations, B-CoreHardening, C-WebUI-Tier1, D-WebUI-Tier2,
    E-WebUI-Tier3, F-TUI, G-Tools, H-Release, T-TeamEdition, V-CrossEdition
[ ] status ∈ {open, in_progress, blocked, done, abandoned}
[ ] owner present (can be "unassigned")
[ ] role ∈ {backend-engineer, frontend-engineer, test-writer, integration, docs, spec-author}
[ ] blocking_on is list (possibly empty), all entries are valid RFC ids
[ ] edition ∈ {pro, team, both} (for T/V RFCs mandatory)
[ ] budget.max_files_touched ≤ 10
[ ] budget.max_new_files ≤ 6
[ ] budget.max_lines_added ≤ 400
[ ] files_to_read is list, all paths exist (or clearly new-in-this-RFC)
[ ] files_will_touch is list, all paths valid
[ ] verify_cmd is runnable (syntax check)
[ ] rollback_cmd restores working tree
[ ] skill_id matches pattern rfc-<id>-<slug>
```

## Step 3 — Body checklist

Validate sections present in order:

```
[ ] # heading matches title
[ ] ## Mission (≤ 30 Chinese chars / 20 English words)
[ ] ## Context (3-5 bullets, cites gap/user-story/audit)
[ ] ## Non-goals (≥ 2 bullets)
[ ] ## Design (single chosen path, no A/B/C discussion)
[ ] ## Steps (numbered, each atomic)
[ ] ## Tests (inline test code or reference to Step N)
[ ] ## Post-checks (human smoke list)
[ ] ## Rollback plan
[ ] ## Updates to other docs
[ ] ## Changelog
```

## Step 4 — Step instruction checklist

For each `Step N` in body:

```
[ ] Step starts with what the step does (1 line)
[ ] Uses only: WRITE <path>, REPLACE <path>, APPEND <path>, RUN <cmd>
[ ] No freestyle instructions like "update X" or "make sure Y"
[ ] REPLACE blocks have both <<<<<<< SEARCH and >>>>>>> REPLACE
[ ] WRITE blocks have a triple-fenced code inside
[ ] RUN commands are in AGENT_EXECUTION_PROTOCOL §6 whitelist
[ ] No command uses && or ; to chain (must be separate RUN)
[ ] No step touches a file outside files_will_touch
[ ] SEARCH blocks are (probably) unique in target files
    (can't fully verify; flag suspicious short patterns)
```

## Step 5 — Executability simulation

Mental walk-through. For each step, ask:
- Could a Qwen-7B-sized model do this without creative interpretation?
- Is the step self-contained (no "figure out where" language)?
- Is the failure mode obvious?

Red flags:
- "Find the X in the file" without exact SEARCH block
- "Add the import if needed" (ambiguous)
- "Similar to how Y works" (requires reasoning)
- Step that depends on runtime output of previous step

## Step 6 — Protocol hazards

Specific to this project:

```
[ ] No RUN command uses pip install / curl / wget / Get-ChildItem -Recurse
[ ] No step tries to grep/find/glob (that's exploration, not execution)
[ ] Any new SQLAlchemy model comes with an alembic migration step
[ ] Any new Pydantic model with async session access uses explicit select, not
    lazy-loaded relationships
[ ] Any Typer command addition registers via @app.command and shows in --help
[ ] New test files under tests/unit/ or tests/integration/
[ ] CHANGELOG update is in Updates to other docs
```

## Step 7 — Produce audit report

```
RFC-<id> <title> — Audit Report

Front-matter: <PASS | FAIL: <items>>
Body structure: <PASS | FAIL: <items>>
Step grammar:  <PASS | FAIL: <items>>
Executability: <PASS | FAIL: <items>>
Protocol hazards: <PASS | FAIL: <items>>

Overall: READY | NOT READY

Blockers (must fix):
  - <item>
Warnings (should fix):
  - <item>
Notes:
  - <item>
```

## Step 8 — Offer next action

- If READY: "Proceed to `exec/rfc/` to execute?"
- If NOT READY: "Route to `plan/` (split) or fix inline? Show diff of what to change?"

## Forbidden

- Do not fix the RFC yourself during audit. Audit is read-only.
- Do not execute verify_cmd as part of audit (that's what `exec/rfc/` Step 5 is for).
- Do not grep the source tree to "verify" whether referenced files exist — just
  check whether they're in files_to_read / files_will_touch.
