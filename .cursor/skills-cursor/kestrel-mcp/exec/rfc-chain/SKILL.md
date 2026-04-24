---
name: kestrel-mcp-exec-rfc-chain
description: >
  Execute a sequence of RFCs sequentially, respecting the blocking_on DAG.
  Trigger on: "run RFC-001 through RFC-005", "按顺序执行 RFC-A04 → T00 → T08",
  "finish Epic A", "跑完 MVP 三件套". Delegates each RFC to exec/rfc/.
---

# Exec RFC Chain — sequential

Run multiple RFCs back-to-back, stopping on first failure.

## Step 1 — Build chain

Parse user input into an ordered list. Forms:
- Explicit: "RFC-A04, RFC-T00, RFC-T08" → use that order
- Range: "RFC-001 through RFC-005" → expand 001→005
- Epic: "Epic A" → read `rfcs/INDEX.md`, take Epic A rows in table order

Validate: for each RFC, `blocking_on` must be `done` or earlier in this chain. If
not, stop and show the broken dependency.

## Step 2 — Confirm plan

Present to user:
```
Chain of <N> RFCs, expected runtime ~<N>*5 = <M> minutes:

  1. RFC-A04  Edition + FeatureFlags  (350 lines, 7 files)
  2. RFC-T00  Team unleashed mode     (180 lines, 6 files)
  3. RFC-T08  Team bootstrap          (260 lines, 5 files)

Proceed? [y/N]
```

**Wait for user confirmation.** Do not auto-proceed on chains > 3 RFCs.

## Step 3 — Iterate

For each RFC `R` in chain:

1. Invoke `exec/rfc/` skill logic for `R`.
2. If `R` succeeds (Step 7 of exec/rfc/ produces clean commit) → continue.
3. If `R` fails (status → blocked) → **stop entire chain**. Do not attempt later RFCs.
4. After each RFC, run **one** `RUN git log -1 --oneline` sanity check.

## Step 4 — Final chain report

```
Chain: <N> RFCs
  ✅ RFC-A04  (12m, 8 files, 340 lines)
  ✅ RFC-T00  (6m,  6 files, 175 lines)
  ❌ RFC-T08  BLOCKED at Step 3 (see RFC file for reason)

Commits:
  abc1234 RFC-A04: Edition + FeatureFlags
  def5678 RFC-T00: Team unleashed mode

Next:
  - Fix RFC-T08 blocker (route to audit/rfc/)
  - Or: human review the two merged commits before continuing
```

## Rules

- **Never skip** an RFC in the chain to "try the next one". Failure halts chain.
- **Never batch commits**. Each RFC = one commit per its own Step 7.
- If 2+ RFCs touch the same file, the RFC that comes later in the chain depends
  on the earlier one's output. Trust the chain order.
- Maximum chain length: **7 RFCs**. More than that → user probably wants
  `exec/rfc-parallel/` or is biting off too much.

## Handoff

- On chain success → `query/` skill reports new `next unblocked`
- On chain failure → `audit/rfc/` skill reviews the blocked RFC
