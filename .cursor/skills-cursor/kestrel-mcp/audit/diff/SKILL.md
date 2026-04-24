---
name: kestrel-mcp-audit-diff
description: >
  Review a git diff or pending changes as a code reviewer would. Trigger on:
  "review my changes", "PR review", "review this diff", "审查这次改动",
  "code review". Delegates style to roles/code-reviewer/.
---

# Audit Diff — PR review

You are code-reviewing uncommitted or committed changes.

## Step 1 — Identify diff scope

Default: pending changes. If user specifies a range, use it:

```
RUN git diff               # default: unstaged
RUN git diff --staged      # if user says "review staged"
RUN git diff HEAD~1 HEAD   # if user says "review last commit"
RUN git diff <sha1>..<sha2> # if specified
```

## Step 2 — Gather context

```
RUN git status --short
RUN git diff --stat <range>
```

Report file count, lines added/removed.

## Step 3 — Match to RFC

For each touched file, check if it's in any RFC's `files_will_touch`:

```
RUN git log -1 --format=%s  # latest commit message (often "RFC-NNN: title")
```

If a commit mentions RFC-NNN, load that RFC to know **what was supposed to change**.
Cross-check: does the diff match `files_will_touch`? Over/under?

## Step 4 — Apply persona

Switch to `roles/code-reviewer/` mental model. Key checks:

### Security
- No new `shell=True` in subprocess
- No new hardcoded credentials / tokens / keys
- No new `except Exception` without specific type
- No new path joins without `safe_path()` for user input
- No new `open()` on user-supplied paths

### Correctness
- Pydantic v2 idioms (`model_validate`, `model_dump`, not v1's `dict()`)
- SQLAlchemy async: no lazy-loaded attribute access in async context
- Structlog usage (not bare `logging.getLogger`)
- Error handling uses `core_errors.*`, not generic Exception

### Test coverage
- Each new public function has a test
- Each new CLI command has a smoke test
- Each new Pydantic model has an instantiation test
- Tests sit in correct `tests/unit/<module>/` or `tests/integration/`

### Style
- `from __future__ import annotations` at top of new Python files
- Google-style docstrings on new public functions
- No commented-out code
- No print statements (use structlog)

### Project-specific
- If new MCP tool: has ToolSpec with rich description fields
  (`when_to_use`, `pitfalls`, `local_model_hints`)
- If new domain entity: has corresponding SQLAlchemy model + test
- If new migration: filename follows Alembic convention
- If config change: `config/default.yaml` + env var documented in `.env.example`

## Step 5 — Output review

```
PR Review — <range> — <N> files, +<A>/-<R> lines

Matches RFC: <RFC-NNN or "unclear">
files_will_touch compliance: <OK | mismatch: <list>>

Findings (by severity):

## Blockers (must fix before merge)
- <file:line> — <issue>

## Concerns (consider before merge)
- <file:line> — <issue>

## Nits (polish, optional)
- <file:line> — <issue>

## Praise (what's done well)
- <file or general observation>

Overall: APPROVE | REQUEST CHANGES | NEEDS WORK
```

## Step 6 — Next action

- If APPROVE: "Commit / push?"
- If REQUEST CHANGES: list specific edits, offer to route to `exec/` for minor
  fixes (but don't auto-edit — review is read-only).

## Forbidden

- **Do not modify code during audit.** Review is read-only.
- Do not re-run `verify_cmd` just to re-verify — that's not the reviewer's job.
- Do not comment on files not in the diff.
- Do not nitpick style that's consistent with nearby code (even if you disagree).
