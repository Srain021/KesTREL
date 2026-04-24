---
name: kestrel-mcp-bootstrap
description: >
  Onboard a new agent or human into the kestrel-mcp project. Load this when the
  user says "开始工作", "new session", "我刚接手", "从哪里开始", "what should I
  read first", "project overview", "boot this project", "bootstrap agent".
  Produces a situational awareness report and recommends next action.
---

# Bootstrap — Kestrel-MCP

You are orienting a fresh agent. Do these steps **in order, no skipping**.

## Step 1 — Read the foundation (exactly these 4 files, nothing else)

Use the Read tool on:

1. `README_FOR_AGENT.md` — project entry
2. `AGENT_EXECUTION_PROTOCOL.md` — how you execute RFCs
3. `PRODUCT_LINES.md` Part 9 — current edition decisions
4. `rfcs/INDEX.md` — RFC status table

**Do not** open other files yet. Do not grep. Do not explore `src/`.

## Step 2 — Check environment

Run (each as a separate Shell call):

```
RUN .venv\Scripts\python.exe --version
RUN git status --short
RUN git log -5 --oneline
RUN .venv\Scripts\python.exe scripts\full_verify.py
```

Capture the output. If `full_verify.py` is not 8/8 green, flag it clearly.

## Step 3 — Situational report

Produce a report in this exact format:

```
╔═══════════════════════════════════════════════════════════╗
║  Kestrel-MCP — Agent Bootstrap Report                    ║
╠═══════════════════════════════════════════════════════════╣
║  Git HEAD:        <sha> "<subject>"                      ║
║  Dirty files:     <count> (list first 5)                 ║
║  full_verify.py:  <8/8 | X/8 ❌>                         ║
║  Python:          <version>                              ║
║  RFCs done:       <count> / <total>                      ║
║  RFCs in_progress: <list>                                ║
║  RFCs blocked:    <list>                                 ║
║  Next unblocked:  <top 3 from INDEX "可并行执行" list>    ║
╚═══════════════════════════════════════════════════════════╝
```

## Step 4 — Recommend

Ask the user exactly one of:

- If `full_verify.py` is red → "**Environment is broken**. Fix it first? Switch to `health/` skill?"
- If any RFC is `in_progress` → "**RFC-NNN is half done**. Resume it (`exec/rfc/`) or abandon?"
- Otherwise → "**Clean slate.** Top 3 candidates: RFC-X, RFC-Y, RFC-Z. Which?"

## Do not

- Read `src/` files during bootstrap. That's the job of `exec/rfc/` once an RFC is chosen.
- Make code changes.
- Start an RFC automatically — the user must pick.

## Post-condition

After bootstrap finishes, one of these skills takes over:
- `exec/rfc/` if user picks an RFC
- `plan/` if user wants to write new RFC
- `audit/` if user wants to inspect
- `handoff/` if user wants to pass to another agent
