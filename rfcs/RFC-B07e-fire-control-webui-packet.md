---
id: RFC-B07e
title: Fire-control packet on findings page
epic: B-CoreHardening
status: done
owner: agent
role: fullstack-engineer
blocking_on: [RFC-B07d]
edition: both
budget:
  max_files_touched: 7
  max_new_files: 2
  max_lines_added: 320
  max_minutes_human: 45
  max_tokens_model: 18000
files_to_read:
  - src/kestrel_mcp/webui/routes/findings.py
  - src/kestrel_mcp/webui/templates/findings/table.html.j2
  - src/kestrel_mcp/webui/templates/findings/_row.html.j2
  - tests/unit/webui/test_finding_routes.py
files_will_touch:
  - rfcs/RFC-B07e-fire-control-webui-packet.md # new
  - src/kestrel_mcp/webui/routes/findings.py
  - src/kestrel_mcp/webui/templates/findings/table.html.j2
  - src/kestrel_mcp/webui/templates/findings/_row.html.j2
  - src/kestrel_mcp/webui/templates/findings/_fire_control.html.j2 # new
  - tests/unit/webui/test_finding_routes.py
  - rfcs/INDEX.md
  - CHANGELOG.md
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/webui/test_finding_routes.py -q
rollback_cmd: |
  git checkout -- src/kestrel_mcp/webui/routes/findings.py src/kestrel_mcp/webui/templates/findings/table.html.j2 src/kestrel_mcp/webui/templates/findings/_row.html.j2 tests/unit/webui/test_finding_routes.py rfcs/INDEX.md CHANGELOG.md
  if exist src\kestrel_mcp\webui\templates\findings\_fire_control.html.j2 del src\kestrel_mcp\webui\templates\findings\_fire_control.html.j2
  if exist rfcs\RFC-B07e-fire-control-webui-packet.md del rfcs\RFC-B07e-fire-control-webui-packet.md
skill_id: rfc-b07e-fire-control-webui-packet
---

# RFC-B07e - Fire-control packet on findings page

## Mission

Render human approval packets from finding readiness cards.

## Context

RFC-B07d shows readiness scores in the findings table. Operators now need one
click to view the approval packet before any high-risk action. The packet is a
decision aid, not a task launcher.

## Non-goals

- No tool execution.
- No approval persistence.
- No background job creation.
- No command generation beyond a human-readable proposed action string.

## Design

Add a GET route returning a partial `_fire_control.html.j2`. Each finding row
gets an HTMX button that targets a page-level `#fire-control-panel`. The packet
includes approval state, proposed action, risk level, evidence gaps, checklist,
rollback/abort guidance, and a clear wait-for-human-approval state.

## Steps

### Step 1 - Add route helper

```
REPLACE src/kestrel_mcp/webui/routes/findings.py
<<<<<<< SEARCH
def _readiness_card(finding: ent.Finding) -> dict[str, object]:
=======
def _readiness_card(finding: ent.Finding) -> dict[str, object]:
>>>>>>> REPLACE
```

### Step 2 - Add fire-control template

```
WRITE src/kestrel_mcp/webui/templates/findings/_fire_control.html.j2
```

### Step 3 - Wire HTMX target and button

```
REPLACE src/kestrel_mcp/webui/templates/findings/table.html.j2
<<<<<<< SEARCH
<div class="bg-white border rounded-xl overflow-hidden">
=======
<section id="fire-control-panel" class="mb-5"></section>

<div class="bg-white border rounded-xl overflow-hidden">
>>>>>>> REPLACE
```

```
REPLACE src/kestrel_mcp/webui/templates/findings/_row.html.j2
<<<<<<< SEARCH
      {% if readiness.first_gap %}
=======
      {% if readiness.first_gap %}
>>>>>>> REPLACE
```

### Step 4 - Add tests and trackers

```
APPEND CHANGELOG.md
```

```
REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-B07d | Readiness cards on findings page | done   | RFC-B07c    | agent |
=======
| RFC-B07d | Readiness cards on findings page | done   | RFC-B07c    | agent |
| RFC-B07e | Fire-control packet on findings  | open   | RFC-B07d    |       |
>>>>>>> REPLACE
```

### Step 5 - Verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/webui/test_finding_routes.py -q
```

## Tests

- Findings list includes a fire-control HTMX button and target panel.
- Fire-control route returns an approval packet for an in-engagement finding.
- Missing or cross-engagement finding still returns 404.

## Notes for executor

- Do not add execution buttons or job creation.
- Keep the packet explicit: `approved=false`, `next_state=wait_for_human_approval`.
- Use only local readiness scoring; no network calls during page render.

## Changelog

- 2026-04-22 - Initial spec.
