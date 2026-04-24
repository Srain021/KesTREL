---
id: RFC-V13c
title: Add HARNESS MCP tools
epic: V-Cross-edition
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-V13b
budget:
  max_files_touched: 8
  max_new_files: 3
  max_lines_added: 400
  max_minutes_human: 60
  max_tokens_model: 20000
files_to_read:
  - src/kestrel_mcp/server.py
  - src/kestrel_mcp/tools/base.py
files_will_touch:
  - rfcs/RFC-V13c-harness-mcp-tools.md # new
  - src/kestrel_mcp/harness/planner.py # new
  - src/kestrel_mcp/harness/module.py # new
  - src/kestrel_mcp/server.py # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_harness_planner.py tests/unit/test_harness_module.py
rollback_cmd: |
  git checkout -- src/kestrel_mcp/server.py
skill_id: rfc-v13c-harness-mcp-tools
---

# RFC-V13c - Add HARNESS MCP tools

## Mission

Provide four public HARNESS tools backed by deterministic planning.

## Design

`harness_start`, `harness_next`, `harness_run`, and `harness_state` live in a
new subsystem. The planner is a small ordered strategy, and `harness_run` uses
the server executor rather than calling low-level handlers directly.

## Tests

`tests/unit/test_harness_planner.py` and `tests/unit/test_harness_module.py`.

## Changelog

- 2026-04-24: Implemented HARNESS tools and central executor reuse.
