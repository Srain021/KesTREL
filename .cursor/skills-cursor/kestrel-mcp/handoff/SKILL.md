---
name: kestrel-mcp-handoff
description: >
  Snapshot current session state for handoff to another agent, OR resume from an
  existing snapshot. Trigger on: "handoff", "交接", "snapshot progress", "save
  state", "resume from snapshot", "恢复", "pick up where X left off", "/compact".
  Writes HANDOFF.md for snapshot, reads it for resume.
---

# Handoff — snapshot + resume

Enables agent-to-agent or session-to-session continuity.

## Decision

| User says | Route |
|-----------|-------|
| "snapshot" / "save" / "交接" / "handoff" | § Snapshot |
| "resume" / "continue from handoff" / "pick up" | § Resume |

---

## § Snapshot — write HANDOFF.md

### Step 1 — Capture state

Run, each Shell call separate:

```
RUN git status --short
RUN git diff --stat
RUN git log -10 --oneline
RUN git branch --show-current
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

Also read current todo list via TodoWrite (internal state).

### Step 2 — Identify active RFC

Check `rfcs/` for any file with `status: in_progress`. If multiple → flag.
If one → that's the active RFC; read its current Step count and note progress.

### Step 3 — Write HANDOFF.md

Overwrite `HANDOFF.md` at repo root with this exact structure:

```markdown
# Handoff Snapshot — <UTC timestamp>

## Git state
- Branch: <name>
- HEAD: <sha> "<subject>"
- Dirty files (<count>):
  - <list, or "clean">
- Last 5 commits:
  - <sha> <subject>

## Baseline health
- full_verify.py: <8/8 ✅ | X/8 ❌>
- Last known-good commit: <sha>

## Active RFC
- <RFC-id> <title>
- Status: <status>
- Step progress: <N / M completed>
- Blocker (if any): <one line>

## Open TODOs
- [x] <done item>
- [ ] <pending item>

## Context notes (free-form, for next agent)
<1-2 paragraphs explaining:
- What was being attempted
- Any tricky decisions just made
- What the next step is
- Any surprises / constraints the next agent should know>

## Restore instructions

Next agent:
1. Read this file (HANDOFF.md)
2. Read the active RFC file if any
3. Run `scripts/full_verify.py` — confirm state matches "Baseline health" above
4. If dirty files list differs from git status, ABORT and ask human
5. Resume from "Next step" section below

## Next step
<exact action: "run Step 5 of RFC-T00" / "start RFC-T08" / "fix failing test tests/unit/foo.py::test_bar">
```

### Step 4 — Commit handoff

```
RUN git add HANDOFF.md
RUN git commit -m "handoff: snapshot at <timestamp>"
```

**Why commit**: so next agent can `git log` to find handoffs. Don't squash
these commits.

### Step 5 — Report

```
Handoff snapshot written: HANDOFF.md
Committed: <sha>

Next agent should:
  1. read HANDOFF.md
  2. confirm `full_verify.py` is 8/8
  3. resume from "Next step"
```

---

## § Resume — read HANDOFF.md

### Step 1 — Load snapshot

Read `HANDOFF.md` at repo root. If missing → stop, tell user "no handoff found".

### Step 2 — Verify state matches

```
RUN git status --short
RUN git log -1 --oneline
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

Compare with HANDOFF.md sections:
- Branch matches?
- HEAD sha is at/after the snapshot's HEAD?
- Dirty files match or are a superset?
- full_verify.py status matches?

If any drift → **stop**, tell user "state diverged since snapshot, need human
review". Do **not** try to reconcile.

### Step 3 — Load active RFC

If snapshot has an active RFC → read that RFC file. Note progress position.

### Step 4 — Restore TODOs

Recreate todo list via TodoWrite based on HANDOFF's "Open TODOs" section.
Mark the done ones as `completed`, pending as `pending`.

### Step 5 — Confirm context

Present to user:

```
Resuming from handoff <timestamp>:
  Active: <RFC-id or "none">
  Next step: <from HANDOFF>
  Environment: <full_verify status>

Proceed with Next step? [y/N]
```

### Step 6 — Execute Next step

On confirmation, route to the appropriate skill:
- If next step is an RFC step → `exec/rfc/`
- If next step is a new RFC → `plan/`
- If next step is a fix → follow the exact instruction verbatim

## Forbidden

- Do not skip Step 2 verification on resume. Stale snapshots = corrupt state.
- Do not delete HANDOFF.md. Each snapshot overwrites the previous; commits
  preserve history.
- Do not snapshot a session with uncommitted multi-RFC changes. First commit the
  finished RFC, then snapshot.
