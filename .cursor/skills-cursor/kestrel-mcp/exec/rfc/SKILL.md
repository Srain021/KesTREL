---
name: kestrel-mcp-exec-rfc
description: >
  Execute a single RFC from d:\TG PROJECT\kestrel-mcp\rfcs\. Load when user says
  "run RFC-NNN", "execute RFC-NNN", "做 RFC-NNN", "implement RFC-NNN", "跑 RFC",
  or when bootstrap routed here. Follows AGENT_EXECUTION_PROTOCOL v1.0. Strict
  8-step protocol. No freestyle.
---

# Exec RFC — single

You are executing **one** RFC. Protocol is from `AGENT_EXECUTION_PROTOCOL.md`.

## Step 1 — Parse RFC id

Extract `RFC-NNN` or `RFC-XNN` from user message. Glob: `rfcs/RFC-<id>-*.md`.
If zero or multiple matches → stop, ask user.

## Step 2 — Load ONLY allowed files

- Read the RFC file fully.
- Parse its YAML front-matter.
- Read every path in `files_to_read`.
- Read `AGENT_EXECUTION_PROTOCOL.md` if not already in context.
- **Do not read anything else.** No grep. No glob beyond above.

## Step 3 — Pre-flight check

Run (each Shell call separate):

```
RUN git status --short
RUN .venv\Scripts\python.exe scripts\full_verify.py
RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-<id>-*.md
```

- If dirty files overlap with `files_will_touch` → stop, tell user "workspace dirty, clean first".
- If `full_verify.py` not 8/8 → stop, "baseline broken, fix with health/ skill first".
- If `validate_rfc.py` exits non-zero → **stop immediately**. The spec is broken
  (phantom paths, non-matching SEARCH, budget overrun, etc). Do NOT attempt
  to fix the RFC mid-execution. Route to `audit/rfc/` skill, mark RFC
  `status: blocked` with `reason: spec_failed_preflight`.
- Record current `git rev-parse HEAD` — you'll reset here if failure.

**This pre-flight step is mandatory as of 2026-04-21** — see
AGENT_EXECUTION_PROTOCOL §5.0 and RFC_AUDIT_PREFLIGHT.md for rationale.

## Step 4 — Execute Steps

For each `Step N` in RFC body, detect the action keyword and act:

| Keyword | Action | Tool |
|---------|--------|------|
| `WRITE <path>` + code block | Create/overwrite | Write tool, verbatim content |
| `REPLACE <path>` + SEARCH/REPLACE block | Atomic edit | StrReplace, SEARCH must match unique |
| `APPEND <path>` + content | Add to end | Read then Write |
| `RUN <cmd>` | Execute | Shell tool |

**Rules**:
- No reordering. Steps are atomic and sequential.
- If `REPLACE` SEARCH doesn't match uniquely → stop at that step, don't "try harder".
- Only touch files in `files_will_touch`. If a step violates this, RFC has a bug — stop.
- Mark each step complete via TodoWrite as you go.

## Step 5 — Run verify_cmd

Run exactly the `verify_cmd` from front-matter, no modifications.

- Exit 0 → proceed to Step 6.
- Exit non-zero → Retry policy (see §8).

## Step 6 — Full regression

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

Must show `Result: 8/8 checks passed.` If red → regression introduced, retry policy.

## Step 7 — Update status + commit

1. Change RFC front-matter `status: open` → `status: done`.
2. Apply items in RFC `Updates to other docs` (CHANGELOG, INDEX, etc.).
3. `git add <files_will_touch> + modified docs`
4. `git commit -m "RFC-NNN: <title>"`
5. `git status` confirms clean.

## Step 8 — Report and stop

Report:
```
RFC-NNN <title>  ✅ DONE
  Files changed: <count from git diff --stat HEAD~1>
  Lines added:   <N> / budget <M>
  Tests added:   <N>
  Next unblocked: <from INDEX>
```

**Stop.** Do not start the next RFC unless user asks explicitly.

## §8 Retry policy

- Attempt up to 3 times. Between attempts: `RUN git checkout -- .` to clean, then re-run Step 4.
- Never modify `verify_cmd`.
- Never rewrite the RFC to pass.
- After 3 fails: set RFC `status: blocked`, append error block per protocol §10, stop.

## Forbidden

- Reading files not in `files_to_read` (including grep-style exploration)
- Installing packages (no `pip install`, no `uv add`)
- Touching files outside `files_will_touch`
- Committing unrelated files
- "Fixing" the RFC itself. If the RFC has a bug → stop and escalate via `audit/rfc/` skill
