---
id: RFC-V13a
title: Add compact tool catalog
epic: V-Cross-edition
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-V13
budget:
  max_files_touched: 6
  max_new_files: 2
  max_lines_added: 300
  max_minutes_human: 45
  max_tokens_model: 16000
files_to_read:
  - src/kestrel_mcp/tools/base.py
  - src/kestrel_mcp/server.py
files_will_touch:
  - rfcs/RFC-V13a-compact-tool-catalog.md # new
  - src/kestrel_mcp/tools/base.py # modified
  - src/kestrel_mcp/tool_catalog.py # new
  - src/kestrel_mcp/resources/__init__.py # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_tool_catalog.py tests/unit/test_resources.py
rollback_cmd: |
  git checkout -- src/kestrel_mcp/tools/base.py src/kestrel_mcp/resources/__init__.py
skill_id: rfc-v13a-compact-tool-catalog
---

# RFC-V13a - Add compact tool catalog

## Mission

Expose a compact local-model tool surface without duplicating guidance.

## Design

`ToolSpec` now owns full and compact rendering plus metadata. `tool_catalog.py`
filters advertised tools according to `llm.tool_exposure`, and `tool://catalog`
plus `tool://{tool_name}/guide` reuse the same `ToolSpec` source.

## Tests

`tests/unit/test_tool_catalog.py` and `tests/unit/test_resources.py`.

## Changelog

- 2026-04-24: Implemented compact catalog and resource exposure.
