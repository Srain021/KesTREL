---
name: kestrel-mcp-team
description: >
  Team Edition operational skills — bootstrap, ops session start, crew handoff.
  Trigger on: "team bootstrap", "start ops", "开始比赛", "team mode", "unleash",
  "launch engagement", "crew session". Assumes `--edition team`.
---

# Team Edition — Operations

Team Edition = **unleashed mode** for internal crew. See `PRODUCT_LINES.md` Part 9.

## Preconditions

This skill assumes:
- RFC-A04 (Edition + FeatureFlags) is done
- RFC-T00 (Unleashed mode) is done
- RFC-T08 (Team bootstrap) is done

If any is missing → route to `exec/rfc/` for the missing one first.

## Decision

| User says | Route |
|-----------|-------|
| "bootstrap engagement X" / "起队伍" | § Bootstrap |
| "start ops session" / "开干" | § Session start |
| "end session" / "收工" | § Session end |
| "crew status" / "who's doing what" | § Crew status |

---

## § Bootstrap

### Step 1 — Gather params

Ask the user (all required):
- `name`: engagement slug (e.g. `op-winter-2026`)
- `scope`: comma-separated patterns (e.g. `target.lab,*.internal`)
- `crew`: comma-separated actor names (e.g. `alice,bob,carol,dave`)

### Step 2 — Verify environment

```
RUN .venv\Scripts\python.exe -m kestrel_mcp.__main__ --edition team show-config
```

Confirm output shows:
- `edition: team`
- `scope_enforcement: warn_only`
- `rate_limit_enabled: false`

If not → environment misconfigured, route to `health/`.

### Step 3 — Run bootstrap

```
RUN .venv\Scripts\python.exe -m kestrel_mcp.__main__ --edition team team bootstrap --name <name> --scope "<scope>"
```

Capture the report. Note the `engagement_id` from output.

### Step 4 — Report to user

```
╔══════════════════════════════════════════════════════════════╗
║  Team Edition Bootstrap — <name>                            ║
╚══════════════════════════════════════════════════════════════╝

Engagement ID:  <uuid>
Scope entries:  <N> (<list>)
Data dir:       ~/.kestrel/data/
Doctor:         <N warnings> (<list or "all clear">)

To start server (stdio transport):
  kestrel --edition team server --engagement <name>

Share with crew:
  Engagement: <name>
  ID: <uuid>
  Scope: <inline>
```

---

## § Session start

### Step 1 — Crew check-in

Ask each crew member (if agent), or prompt human operator:
- Who's on console right now?
- What role tonight? (recon / exploitation / post-exploitation / note-taker)

### Step 2 — Create session record

```
RUN .venv\Scripts\python.exe -m kestrel_mcp.__main__ --edition team session new --engagement <name> --operator <actor>
```

(Placeholder — may need RFC-T05 for full actor tracking. Use simple `session new`
if available, otherwise skip and note the session verbally.)

### Step 3 — Load tools for role

Based on declared role, remind operator of primary tools (MCP tool names):

- **recon**: `shodan_search`, `nuclei_scan`, `engagement_new`, `target_list`
- **exploitation**: `sliver_generate_implant`, `caido_start`, `nuclei_scan`
- **post-ex**: `sliver_interact`, `sliver_tasks`, `ligolo_generate_agent_command`
- **note-taker**: `engagement_update`, `finding_new`, `artifact_add`

### Step 4 — Start clock

```
RUN git log -1 --format='%H %s'
```

Note the starting HEAD so post-session reports can diff.

### Step 5 — Announce ready

```
Ready to engage.
  Operator: <actor>
  Role: <role>
  Engagement: <name>
  Tools primed: <list>

When done, say "end session" to wrap up.
```

---

## § Session end

### Step 1 — Snapshot findings

```
RUN .venv\Scripts\python.exe -m kestrel_mcp.__main__ --edition team finding_list --engagement <name>
RUN .venv\Scripts\python.exe -m kestrel_mcp.__main__ --edition team target_list --engagement <name>
```

Capture outputs.

### Step 2 — Session report

```
Session Summary — <engagement> — <duration>

Findings created: <N> (<severity breakdown>)
Targets added: <N>
Tools called: <N> (<top 5 by count>)

Open items for next session:
  <from pending findings / targets without enrichment>

Data dir: ~/.kestrel/data/
```

### Step 3 — Handoff?

Ask: "Handoff to another operator? [y/N]"

If yes → route to `handoff/SKILL.md` § Snapshot.

---

## § Crew status

### Step 1 — Read engagement state

```
RUN .venv\Scripts\python.exe -m kestrel_mcp.__main__ --edition team engagement_get --name <current_engagement>
```

### Step 2 — Report

Present a live dashboard-style output (text only — CLI-friendly):

```
Engagement: <name> (status: <active|paused|closed>)
  Started:     <timestamp>
  Operators:   <list>
  Targets:     <N in scope, M discovered>
  Findings:    <N open, M verified, K remediated>
  Last action: <timestamp> (<tool_name>)
```

---

## Forbidden in Team mode

Even though Team is "unleashed", these still apply:

- **Do not disable the cost ledger.** You want to know your LLM bill.
- **Do not disable `untrust_wrap_tool_output`.** Prompt injection from targets
  is still real, even when scope is open.
- **Do not commit raw flag values or credentials to git.** Even if encryption is
  off, shared repos are public attack surface.
- **Do not push team engagement data to the Pro branch.** Cross-contamination.

## When to route back to Pro

If user says "this is for a paying client" mid-session → stop, route to
`health/`, switch edition to Pro, rerun bootstrap under pro edition.
