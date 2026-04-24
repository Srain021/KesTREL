---
name: kestrel-mcp-exec-rfc-parallel
description: >
  Execute multiple independent RFCs in parallel using git worktrees. Trigger on:
  "并行跑 RFC-G01/G03/G04", "parallel RFCs", "run these in worktrees", "batch
  execute独立 RFC". Uses dispatching-parallel-agents pattern. Safe only for
  RFCs with no overlapping files_will_touch.
---

# Exec RFC Parallel — worktree fanout

Run multiple RFCs simultaneously in isolated worktrees. **Only for RFCs that
touch disjoint file sets.**

## Step 1 — Collision check

For each requested RFC, parse its `files_will_touch`. If any file appears in 2+
RFCs → **abort parallel mode**, suggest chain mode instead.

Also check `blocking_on`: all deps must be `done` (parallel can't satisfy a
dep inside the batch).

## Step 2 — Present plan

```
Parallel execution plan:
  worktree-1: RFC-G01 (subfinder tool)          4 files, 120 lines
  worktree-2: RFC-G03 (nmap wrapper)            5 files, 180 lines
  worktree-3: RFC-G04 (ffuf wrapper)            3 files,  90 lines
  worktree-4: RFC-B03 (threat model docs)       1 file,   40 lines

No file collisions detected. Proceed? [y/N]
```

**Wait for confirmation.**

## Step 3 — Spawn worktrees

For each RFC, create an isolated worktree:

```
RUN git worktree add ..\kestrel-wt-<id> -b rfc-<id> HEAD
```

This creates `d:\TG PROJECT\kestrel-wt-G01`, etc. Each gets its own branch
`rfc-G01`.

## Step 4 — Dispatch subagents

Use the Task tool with `subagent_type=generalPurpose` and a detailed prompt per
RFC. Each subagent receives:

```
You are in worktree d:\TG PROJECT\kestrel-wt-<id>.
Load skill: kestrel-mcp/exec/rfc/ (AGENT_EXECUTION_PROTOCOL).
Execute RFC-<id> per its file.
When done: do NOT push; just commit to branch rfc-<id>. Report back status
(done | blocked) and commit SHA.
```

Dispatch all in one tool call batch. Set `run_in_background: true` for each.

## Step 5 — Await + triage

Poll subagents until all complete (Await tool, max 30 min each).

For each:
- ✅ Returned "done" → collect its commit SHA.
- ❌ Returned "blocked" → note the reason, leave worktree for human review.

## Step 6 — Merge successful branches

Return to main worktree:

```
RUN git checkout main
```

Merge each successful `rfc-<id>` branch:

```
RUN git merge rfc-<id> --no-ff -m "Merge RFC-<id>: <title>"
```

Between each merge, run `scripts\full_verify.py`. If red → abort merge,
investigate (worktree conflict or test regression).

## Step 7 — Cleanup

For each done RFC:
```
RUN git worktree remove ..\kestrel-wt-<id>
```

Leave failed ones intact for human review; tell user their paths.

## Step 8 — Chain report

```
Parallel batch: 4 RFCs
  ✅ RFC-G01  merged (abc1234)
  ✅ RFC-G03  merged (def5678)
  ✅ RFC-G04  merged (fed2345)
  ❌ RFC-B03  blocked in worktree-4 at Step 2 (see worktree)

Merged: 3 / 4
Total lines added: 390
Regression: 8/8 green

Leftover worktrees for review:
  d:\TG PROJECT\kestrel-wt-B03/  (branch rfc-B03)
```

## Rules

- **Max 4 parallel** worktrees. Windows file locking + pytest runs make more
  unreliable.
- **Never merge a worktree whose RFC went blocked**. Human reviews first.
- **Merges are sequential** even though execution is parallel — each merge must
  preserve `full_verify.py` green.
- If a subagent goes silent > 30 min: kill via `RUN git worktree remove --force`,
  mark RFC blocked.

## When to use chain vs parallel

| Use chain | Use parallel |
|----------|--------------|
| RFCs have `blocking_on` between them | RFCs are fully independent |
| Touch same files | Touch disjoint files |
| < 4 RFCs | 4+ independent RFCs |
| Need reviewer to see each in isolation | Trust the RFCs are complete |
