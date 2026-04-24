---
id: RFC-V13b
title: Add HARNESS SQLite state
epic: V-Cross-edition
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-V13
budget:
  max_files_touched: 7
  max_new_files: 3
  max_lines_added: 400
  max_minutes_human: 45
  max_tokens_model: 16000
files_to_read:
  - src/kestrel_mcp/domain/entities.py
  - src/kestrel_mcp/domain/storage.py
files_will_touch:
  - rfcs/RFC-V13b-harness-sqlite-state.md # new
  - src/kestrel_mcp/domain/entities.py # modified
  - src/kestrel_mcp/domain/storage.py # modified
  - src/kestrel_mcp/domain/services/harness_service.py # new
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/domain/test_harness_service.py
rollback_cmd: |
  git checkout -- src/kestrel_mcp/domain/entities.py src/kestrel_mcp/domain/storage.py
skill_id: rfc-v13b-harness-sqlite-state
---

# RFC-V13b - Add HARNESS SQLite state

## Mission

Persist HARNESS sessions and planned steps in SQLite.

## Design

The domain layer gains `HarnessSession`, `HarnessStep`, enums, ORM rows, an
Alembic migration, and a small `HarnessService`. It keeps business logic out of
the ORM model and exposes a compact state payload for MCP resources.

## Tests

`tests/unit/domain/test_harness_service.py`.

## Changelog

- 2026-04-24: Implemented HARNESS persistence service.
