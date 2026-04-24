---
id: RFC-V13d
title: Add HARNESS smoke coverage and docs
epic: V-Cross-edition
status: done
owner: agent
role: backend-engineer
blocking_on:
  - RFC-V13c
budget:
  max_files_touched: 8
  max_new_files: 3
  max_lines_added: 400
  max_minutes_human: 45
  max_tokens_model: 16000
files_to_read:
  - docs/user-manual.zh-CN.md
  - CHANGELOG.md
files_will_touch:
  - rfcs/RFC-V13d-harness-smoke-docs.md # new
  - docs/user-manual.zh-CN.md # modified
  - CHANGELOG.md # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_tool_catalog.py tests/unit/test_harness_module.py
rollback_cmd: |
  git checkout -- docs/user-manual.zh-CN.md CHANGELOG.md
skill_id: rfc-v13d-harness-smoke-docs
---

# RFC-V13d - Add HARNESS smoke coverage and docs

## Mission

Document the local-model profile and protect it with smoke tests.

## Design

The docs describe the `llm` profile, the four HARNESS MCP tools, and the new
resource URIs. Tests assert compact output is smaller, local exposure hides
low-level scan tools, and HARNESS records internal ToolInvocation rows.

## Tests

Targeted pytest coverage plus CLI list-tools regression.

## Changelog

- 2026-04-24: Added HARNESS smoke tests and manual notes.
