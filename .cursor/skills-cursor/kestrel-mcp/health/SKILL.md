---
name: kestrel-mcp-health
description: >
  Verify project health or rollback changes. Trigger on: "full_verify", "健康
  检查", "are we green", "run all tests", "rollback", "回滚", "undo uncommitted",
  "reset working tree", "baseline check".
---

# Health — verify or rollback

Two modes: verify or rollback. Never both at once.

## Decision

| User says | Route |
|-----------|-------|
| "verify" / "health check" / "健康检查" / "are we green" | § Verify |
| "rollback" / "undo" / "回滚" / "reset" / "abandon changes" | § Rollback |

---

## § Verify

### Step 1 — Baseline

```
RUN git status --short
```

Record dirty file count.

### Step 2 — Core check

```
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

Interpret output. Expected: `Result: 8/8 checks passed.`

### Step 3 — Extended checks (optional)

If `full_verify.py` is green and user asks for "deep check":

```
RUN .venv\Scripts\pytest.exe tests/ -x --tb=short -q
RUN .venv\Scripts\ruff.exe check src/
RUN .venv\Scripts\mypy.exe src/redteam_mcp/core/ src/redteam_mcp/domain/
```

### Step 4 — Report

```
Health Report — <timestamp>

full_verify.py: <8/8 ✅ | X/8 ❌ (which failed)>
pytest:         <N passed, M failed, K skipped>  (if run)
ruff:           <clean | N issues>  (if run)
mypy:           <clean | N errors>  (if run)

Git: <clean | dirty: list>
```

### Step 5 — Recommend

- Green → "Safe to start new RFC. Route to `query/` for next step?"
- Red → Identify the failing check. Route to `audit/diff/` if dirty,
  or propose a fix RFC if baseline problem.

---

## § Rollback

**Dangerous operation.** Always confirm before executing.

### Step 1 — Inventory what's at risk

```
RUN git status --short
RUN git diff --stat
RUN git stash list
```

Present to user:

```
About to discard:
  Modified files (N):
    src/foo.py (+12 -3)
    ...
  Untracked files (M):
    tests/new_test.py
    ...
  Existing stashes: <N>

This CANNOT be undone. Confirm rollback? [y/N]
```

**Wait for explicit "yes" / "y". No auto-proceed.**

### Step 2 — Determine rollback scope

| User wants | Command |
|-----------|---------|
| "rollback this RFC" | `RUN git checkout -- <files from RFC's files_will_touch>` |
| "rollback all uncommitted" | `RUN git checkout -- .` + `RUN git clean -fd` |
| "rollback last commit" | Only if commit is by current agent + not pushed — `RUN git reset --soft HEAD~1` (keeps changes staged) |
| "nuke last commit" | `RUN git reset --hard HEAD~1` — **extra confirmation** |

### Step 3 — Execute

Run chosen command. Then:

```
RUN git status --short
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

### Step 4 — Report

```
Rollback complete.
  Discarded: <N> modified files, <M> untracked
  Current HEAD: <sha> "<subject>"
  Baseline: <8/8 ✅ | X/8>
```

### Step 5 — Update RFC status

If rollback was because of an RFC failure:
- Open the RFC file
- If status was `in_progress` → change to `open` (preserve for retry)
- If status was already `blocked` → keep blocked, add note about rollback

### Post-condition

After rollback, route to:
- `query/` — see what's still actionable
- `audit/rfc/` — diagnose why the RFC failed

---

## Forbidden

- Never rollback pushed commits without user saying "force push" explicitly
- Never rollback across a `handoff: snapshot` commit without asking (those are
  intentional milestones)
- Never run `git clean -fdx` (removes .venv too — disaster)
- Never skip Step 2 of § Verify. `full_verify.py` is the authoritative signal
