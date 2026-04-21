---
id: RFC-B07d
title: Readiness cards on findings page
epic: B-CoreHardening
status: done
owner: agent
role: fullstack-engineer
blocking_on: [RFC-B07c]
edition: both
budget:
  max_files_touched: 7
  max_new_files: 1
  max_lines_added: 260
  max_minutes_human: 45
  max_tokens_model: 18000
files_to_read:
  - src/kestrel_mcp/webui/routes/findings.py
  - src/kestrel_mcp/webui/templates/findings/table.html.j2
  - src/kestrel_mcp/webui/templates/findings/_row.html.j2
  - tests/unit/webui/test_finding_routes.py
files_will_touch:
  - rfcs/RFC-B07d-readiness-webui-cards.md # new
  - src/kestrel_mcp/webui/routes/findings.py
  - src/kestrel_mcp/webui/templates/findings/table.html.j2
  - src/kestrel_mcp/webui/templates/findings/_row.html.j2
  - tests/unit/webui/test_finding_routes.py
  - rfcs/INDEX.md
  - CHANGELOG.md
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/webui/test_finding_routes.py -q
rollback_cmd: |
  git checkout -- src/kestrel_mcp/webui/routes/findings.py src/kestrel_mcp/webui/templates/findings/table.html.j2 src/kestrel_mcp/webui/templates/findings/_row.html.j2 tests/unit/webui/test_finding_routes.py rfcs/INDEX.md CHANGELOG.md
  if exist rfcs\RFC-B07d-readiness-webui-cards.md del rfcs\RFC-B07d-readiness-webui-cards.md
skill_id: rfc-b07d-readiness-webui-cards
---

# RFC-B07d - Readiness cards on findings page

## Mission

Show B07 readiness assessments beside every Web UI finding.

## Context

RFC-B07a/B07b/B07c added the readiness brain and MCP advisory tools. Operators
also need the Web UI to show whether a finding is parked, needs investigation,
is ready to validate, or requires operator review before high-risk action.

## Non-goals

- No Web UI tool execution button.
- No EPSS/KEV network lookup from page render.
- No database migration.
- No finding status mutation beyond existing transition form.

## Design

Compute local `assess_exploitability(finding)` values in the findings route and
pass them into the row template keyed by finding id. Add a compact Readiness
column showing score, rating, human-approval requirement, and first evidence
gap or next step.

## Steps

### Step 1 - Add route-side readiness assessment

```
REPLACE src/kestrel_mcp/webui/routes/findings.py
<<<<<<< SEARCH
from ...core import RequestContext
from ...domain import entities as ent
=======
from ...analysis import assess_exploitability
from ...core import RequestContext
from ...domain import entities as ent
>>>>>>> REPLACE
```

### Step 2 - Add template column

```
REPLACE src/kestrel_mcp/webui/templates/findings/table.html.j2
<<<<<<< SEARCH
        <th class="px-3 py-2 text-left">Tool</th>
        <th class="px-3 py-2 text-left">Status</th>
=======
        <th class="px-3 py-2 text-left">Tool</th>
        <th class="px-3 py-2 text-left">Readiness</th>
        <th class="px-3 py-2 text-left">Status</th>
>>>>>>> REPLACE
```

### Step 3 - Update row rendering

```
REPLACE src/kestrel_mcp/webui/templates/findings/_row.html.j2
<<<<<<< SEARCH
  <td class="px-3 py-2">{{ f.discovered_by_tool }}</td>
  <td class="px-3 py-2">
=======
  <td class="px-3 py-2">{{ f.discovered_by_tool }}</td>
  <td class="px-3 py-2">
>>>>>>> REPLACE
```

### Step 4 - Add tests and trackers

```
APPEND CHANGELOG.md
```

```
REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-B07c | Offensive readiness MCP tools    | done   | RFC-B07b    | agent |
=======
| RFC-B07c | Offensive readiness MCP tools    | done   | RFC-B07b    | agent |
| RFC-B07d | Readiness cards on findings page | open   | RFC-B07c    |       |
>>>>>>> REPLACE
```

### Step 5 - Verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/webui/test_finding_routes.py -q
```

## Tests

- Findings list renders a Readiness column.
- Critical verified finding renders ready-to-validate and score text.
- Transition partial row includes updated readiness card.

## Notes for executor

- Keep route-side assessment local only; no network enrichment in page render.
- Avoid adding execution affordances to the findings page.
- Row partial must include the same `readiness_by_id` key as full table render.

## Changelog

- 2026-04-22 - Initial spec.
