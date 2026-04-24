---
id: RFC-V13
title: Add HARNESS local model runtime
epic: V-Cross-edition
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-A04
  - RFC-002
budget:
  max_files_touched: 8
  max_new_files: 4
  max_lines_added: 400
  max_minutes_human: 60
  max_tokens_model: 20000
files_to_read:
  - AUDIT_V2.md
  - rfcs/INDEX.md
  - src/kestrel_mcp/server.py
files_will_touch:
  - rfcs/RFC-V13-HARNESS-local-model-runtime.md # new
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_tool_catalog.py tests/unit/test_harness_module.py
rollback_cmd: |
  git checkout -- rfcs/RFC-V13-HARNESS-local-model-runtime.md
skill_id: rfc-v13-harness-local-model-runtime
---

# RFC-V13 - Add HARNESS local model runtime

## Mission

Add a small persisted HARNESS layer for local and mixed-model operation.

## Context

This closes the first MVP slice across the AUDIT_V2 gaps for mixed-model
routing, subtask guidance, tool complexity metadata, soft timeout metadata, and
benchmark smoke coverage. The implementation is advisory: it returns
`recommended_model_tier` but does not call any external LLM provider.

## Design

HARNESS is split into four executable slices:

- RFC-V13a: compact tool catalog and guide resources.
- RFC-V13b: SQLite session and step persistence.
- RFC-V13c: public HARNESS MCP tools and deterministic planner.
- RFC-V13d: smoke tests and manual updates.

The runtime keeps low-level execution inside the central server executor so
scope checks, rate limits, and ToolInvocation audit records remain shared.

## Tests

Focused unit tests cover catalog rendering, exposure filtering, resources,
HARNESS persistence, planner behavior, confirmation gates, and server-level
ToolInvocation recording.

## Changelog

- 2026-04-24: Implemented MVP runtime.
