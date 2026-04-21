---
id: RFC-B05b2
title: Tool guidance completeness - Sliver ops tools (4 of 8)
epic: B-CoreHardening
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-B05b1]
edition: both
budget:
  max_files_touched: 5
  max_new_files: 1
  max_lines_added: 400
  max_minutes_human: 45
  max_tokens_model: 22000
files_to_read:
  - src/kestrel_mcp/tools/sliver_tool.py
  - tests/unit/tools/test_sliver_tool.py
  - rfcs/RFC-B05b1-sliver-server-guidance.md
files_will_touch:
  - rfcs/RFC-B05b2-sliver-ops-guidance.md
  - src/kestrel_mcp/tools/sliver_tool.py
  - tests/unit/tools/test_sliver_tool.py
  - rfcs/INDEX.md
  - CHANGELOG.md
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/tools/test_sliver_tool.py -v
rollback_cmd: |
  git checkout -- src/kestrel_mcp/tools/sliver_tool.py tests/unit/tools/test_sliver_tool.py rfcs/INDEX.md CHANGELOG.md
  if exist rfcs\RFC-B05b2-sliver-ops-guidance.md del rfcs\RFC-B05b2-sliver-ops-guidance.md
skill_id: rfc-b05b2-sliver-ops-guidance
---

# RFC-B05b2 - Sliver ops guidance

## Mission

Complete the B05b Sliver guidance pass by documenting the remaining four
operator tools:

- `sliver_list_sessions`
- `sliver_list_listeners`
- `sliver_generate_implant`
- `sliver_execute_in_session`

This RFC is intentionally guidance-only. It does not add new post-exploitation
capability, change subprocess invocation, or alter handler behavior.

## Context

RFC-B05b1 completed the server lifecycle and raw-command tools. The remaining
Sliver ops tools are more sensitive because they cover implant generation and
session-scoped command execution. Thin MCP descriptions here can cause weak
models to skip readiness checks, pick the wrong session, generate payloads
before listeners exist, or embed secrets in audited command strings.

## Non-goals

- No handler logic changes.
- No new Sliver commands.
- No Sliver runtime smoke tests.
- No changes to C2 defaults, payload evasion behavior, or scope semantics.

## Design

Update the four remaining `ToolSpec` entries in `sliver_tool.py`.

Minimum standard:

- Dangerous tools (`sliver_generate_implant`, `sliver_execute_in_session`) must
  include all guidance fields plus `example_conversation`.
- Non-dangerous ops inventory tools must include at least `when_to_use`,
  `prerequisites`, `follow_ups`, `pitfalls`, and `local_model_hints`.
- Every JSON schema property must have a self-documenting `description`.

The guidance emphasizes:

- explicit authorized-scope checks and callback ownership;
- listener/session verification before destructive or high-risk operations;
- audit-log sensitivity for command strings;
- safe default examples using benign lab commands;
- cleanup and artifact tracking after payload generation.

## Steps

1. Patch `sliver_list_sessions` and `sliver_list_listeners` ToolSpecs with
   readiness/inventory guidance.
2. Patch `sliver_generate_implant` ToolSpec with full guidance and parameter
   descriptions.
3. Patch `sliver_execute_in_session` ToolSpec with full guidance and parameter
   descriptions.
4. Expand `tests/unit/tools/test_sliver_tool.py` from B05b1-only coverage to
   all 8 Sliver tools.
5. Update `rfcs/INDEX.md` and `CHANGELOG.md`.
6. Run the verify command and `scripts/full_verify.py`.

## Tests

The Sliver regression guard should assert:

- all 8 Sliver tools exist;
- all dangerous Sliver tools have full guidance and examples;
- non-dangerous Sliver tools have core guidance;
- all schema properties have descriptions.

## Notes for executor

- Keep examples benign and scoped to lab/CTF-style usage.
- Do not include credential material in examples.
- Do not weaken existing scope checks or remove `requires_scope_field` from
  `sliver_generate_implant`.
- `sliver_execute_in_session` has no target field by design; guidance must
  force a prior `sliver_list_sessions` call and explicit session selection.

## Changelog

- 2026-04-22 - Initial spec for B05b2 Sliver ops guidance.
