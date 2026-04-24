---
name: kestrel-mcp-query
description: >
  Answer status questions about RFCs, threats, next steps. Trigger on: "RFC 进度",
  "what's done", "next unblocked", "查 RFC", "list open RFCs", "threat model
  status", "哪些可以并行", "what should I do next", "progress report".
---

# Query — status and routing

Read-only information lookup. Route to the right internal query.

## Decision tree

| User asks about | Section |
|-----------------|---------|
| RFC status / list / what's done | § A |
| What to do next / unblocked RFCs | § B |
| Threat model status | § C |
| Project metrics (tests, LOC, coverage) | § D |
| Edition config (pro vs team settings) | § E |

---

## § A — RFC status

### Step 1

Read `rfcs/INDEX.md`.

### Step 2 — Filter by user request

- "all" → full table
- "done" → rows with status=done
- "open" → rows with status=open
- "blocked" → rows with status=blocked, include reason from RFC file
- "in_progress" → rows with status=in_progress, include progress
- Epic-scoped ("Epic T", "Team RFCs") → filter by epic column

### Step 3 — Render table

```
RFCs — <filter>

| ID      | Title              | Status      | Blocking on | Owner |
|---------|--------------------|-------------|-------------|-------|
| RFC-A04 | Edition + Flags    | open        | RFC-002     | —     |
| ...     | ...                | ...         | ...         | ...   |

Stats: <N> done / <M> open / <K> blocked
```

---

## § B — What to do next

### Step 1

Read `rfcs/INDEX.md`. Parse "可并行执行" section plus any new additions.

### Step 2 — Compute unblocked

For each status=open RFC:
- Check `blocking_on` — if all are status=done → unblocked
- Collect into unblocked list

### Step 3 — Rank by priority

Ranking (high → low):
1. Team MVP critical path: RFC-A04 > RFC-T00 > RFC-T08
2. Epic A before others (foundation)
3. Small budget before large (fast wins)
4. Dependencies of many others (unblocks more)

### Step 4 — Present top 3

```
Next unblocked (ranked):

1. RFC-A04 — Edition + FeatureFlags (280 lines, ~45 min)
   Unblocks: RFC-T00, RFC-T08, all V-series, all T-series
   Recommended: START HERE

2. RFC-001 — uv lock (40 lines, ~15 min)
   Unblocks: RFC-002 → CI → everything

3. RFC-V10 — License matrix (docs only, ~30 min)
   Unblocks: nothing, but pure docs → safe warm-up

Pick one? Or show alternatives?
```

---

## § C — Threat model status

### Step 1

Read `THREAT_MODEL.md` if exists. Else `AUDIT.md`'s security section.

### Step 2 — Filter

- "open threats" → status ≠ mitigated
- "all" → full table
- "critical" → severity=critical

### Step 3 — Render + cross-reference

For each threat, check if a closing RFC exists:

```
T-1 Subprocess injection via tool args
  Severity: high
  Status:   open
  Mitigation: none yet
  Related RFC: RFC-B05 (Subprocess stderr redaction) — partial
  Recommendation: draft new RFC for argv-only quoting

T-2 ...
```

---

## § D — Project metrics

Run:

```
RUN .venv\Scripts\python.exe -m pytest --collect-only -q
RUN .venv\Scripts\python.exe -c "import subprocess,pathlib; files = list(pathlib.Path('src').rglob('*.py')); print(f'Python files: {len(files)}'); lines = sum(len(f.read_text(encoding=\"utf-8\").splitlines()) for f in files); print(f'Total lines: {lines}')"
```

Present:

```
Kestrel-MCP Metrics

Source:
  Python files:  <N>
  Lines of code: <N>
  MCP tools:     <N> (across <M> modules)

Tests:
  Collected: <N>
  Last run:  <8/8 ✅ | X/8 ❌>

RFCs:
  Total:       <N>
  Done:        <N>
  In progress: <N>
  Blocked:     <N>

Docs:
  RFC files:       <N>
  Skill files:     <N>
  Audit versions:  2 (v1, v2)
```

---

## § E — Edition config

Run:

```
RUN .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition pro show-config
RUN .venv\Scripts\python.exe -m redteam_mcp.__main__ --edition team show-config
```

(If `show-config` doesn't exist yet, RFC-A04 not done; say so.)

Diff them, present:

```
Edition differences:

Field                            | Pro       | Team
---------------------------------|-----------|------------
scope_enforcement                | strict    | warn_only
rate_limit_enabled               | true      | false
credential_encryption_required   | true      | false
...
```

---

## Forbidden

- Do not modify any files during query.
- Do not run `verify_cmd` or tests beyond `--collect-only`.
- Do not read into `src/` files unless § E needs it (and only `redteam_mcp.__main__`).
- Do not recommend an RFC whose `blocking_on` isn't all done.
