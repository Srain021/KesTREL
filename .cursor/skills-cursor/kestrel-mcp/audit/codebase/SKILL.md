---
name: kestrel-mcp-audit-codebase
description: >
  Perform a codebase audit in the style of AUDIT.md / AUDIT_V2.md. Find gaps,
  risks, dead code, non-idiomatic patterns. Trigger on: "audit 代码库", "查漏补缺",
  "find gaps", "security review", "code smell audit", "审计项目".
---

# Audit Codebase

You are a senior auditor. Read-only. Produce findings + RFC proposals.

## Step 1 — Scope

Ask the user: "Scope of audit?"

Options:
- `all` — full codebase scan (uses AUDIT_V2's template)
- `security` — threat model + redact + scope + subprocess only
- `domain` — entities + services + storage
- `tools/` — MCP tool modules
- `webui/` — FastAPI + templates
- `tests/` — coverage + quality
- `<specific path>`

## Step 2 — Read baseline

Always read **before** touching code:
- `AUDIT.md` (v1 — 13 internal gaps)
- `AUDIT_V2.md` (v2 — 28 ecosystem gaps)
- `rfcs/INDEX.md` (what RFCs already cover gaps)
- `CHANGELOG.md`

This tells you what is **already known**. Do not re-report known gaps — verify
their status.

## Step 3 — Scan (read-only, do not modify)

Depending on scope, read key files with Read tool:

| Scope | Files |
|-------|-------|
| security | `src/kestrel_mcp/security.py`, `core/redact.py`, `core/paths.py`, `executor.py` |
| domain | `src/kestrel_mcp/domain/entities.py`, `services/*.py`, `storage.py` |
| tools | `src/kestrel_mcp/tools/__init__.py`, any flagged tool_*.py |
| webui | `src/kestrel_mcp/webui/app.py`, `routes/*.py`, templates |
| tests | `pytest --collect-only -q` then sample 3 directories |

Use `Grep` for specific patterns (**only** for audit findings, not exploration):
- `except Exception` without specific type → smell
- `shell=True` in subprocess → security
- `password=` / `token=` / hardcoded keys → secrets
- `# TODO` / `# FIXME` / `# HACK` → inventory
- `lazy=` in sqlalchemy models → async traps

## Step 4 — Categorize findings

Every finding:

```
### F-<N> | <short title>

**Category**: bug | security | design | perf | maintainability | docs | dead-code
**Severity**: critical | high | medium | low
**Location**: <file>:<line_range>
**Evidence**: <snippet or grep result>
**Impact**: <1-2 sentences>
**Existing RFC**: <ID or "none">
**Proposed fix**: <short — may become new RFC>
```

## Step 5 — Deduplicate vs known

For each finding, cross-check:
- In `AUDIT.md` D-1..D-13? → link, don't re-report
- In `AUDIT_V2.md` V-/T-/D- sections? → link, don't re-report
- Covered by open RFC? → link, don't re-report
- **Genuinely new** → include in output

## Step 6 — Produce report

Write to **console only** (do NOT write a new AUDIT file without user OK).
Format:

```
Codebase Audit — <timestamp> — Scope: <scope>

Summary:
  Critical: <N>
  High:     <N>
  Medium:   <N>
  Low:      <N>
  Total new findings: <N> (excluding <M> already tracked)

New findings:
  [F-1..F-N with full blocks]

Already tracked (for reference):
  - D-5 (AUDIT.md): <status in INDEX>
  - V-C1 (AUDIT_V2.md): <status>

Recommended RFCs to draft:
  1. RFC for F-1 + F-2 (combined: <group reason>)
  2. RFC for F-3 (standalone)
  ...
```

## Step 7 — Offer next action

Ask user one of:
- "Draft RFCs for findings F-1..F-N?" → route to `plan/`
- "Update AUDIT_V2.md with these findings?" → approve before writing
- "Ignore / keep as observation?" → stop

## Forbidden

- Do not modify source code during audit
- Do not run `full_verify.py` or tests (you're auditing, not fixing)
- Do not grep `node_modules/`, `.venv/`, `.git/` — waste of tokens
- Do not speculate without evidence; each finding needs a file:line pointer or grep result
