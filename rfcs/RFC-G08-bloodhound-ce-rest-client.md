---
id: RFC-G08
title: BloodHound-CE REST client
epic: G-Tool-expansion
status: done
owner: agent
role: backend-engineer
blocking_on: []
edition: both
budget:
  max_files_touched: 10
  max_new_files: 2
  max_lines_added: 320
  max_minutes_human: 45
  max_tokens_model: 12000
files_to_read:
  - src/kestrel_mcp/tools/impacket_tool.py
  - src/kestrel_mcp/tools/__init__.py
  - config/default.yaml
  - pyproject.toml
files_will_touch:
  - rfcs/RFC-G08-bloodhound-ce-rest-client.md # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md             # modified
  - rfcs/INDEX.md                             # modified
  - CHANGELOG.md                              # modified
  - TOOLS_MATRIX.md                           # modified
  - config/default.yaml                       # modified
  - src/kestrel_mcp/tools/__init__.py         # modified
  - src/kestrel_mcp/tools/bloodhound_tool.py  # new
  - tests/unit/tools/test_bloodhound_tool.py  # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/tools/test_bloodhound_tool.py -q
rollback_cmd: git checkout -- .
skill_id: rfc-g08-bloodhound-ce-rest-client
---

# RFC-G08 - BloodHound-CE REST client

## Mission

Add an opt-in BloodHound-CE REST client wrapper.

## Context

- BloodHound-CE is usually run by the operator in Docker.
- Kestrel should not manage that container in this RFC; it only talks to the
  configured API URL.
- Existing Python `httpx` dependency is sufficient; no new dependency needed.

## Non-goals

- Do not start/stop Docker Compose.
- Do not upload SharpHound collections.
- Do not implement full BloodHound API coverage.

## Design

Create `BloodHoundModule` with:

- `bloodhound_query(cypher, engagement_id)`
- `bloodhound_list_datasets()`
- `bloodhound_version()`

Config uses `tools.bloodhound.api_url` and `tools.bloodhound.api_key`. Tests
mock `httpx.AsyncClient` with a small fake client.

## Steps

### Step 1 - Add default config

REPLACE config/default.yaml
<<<<<<< SEARCH
  impacket:
    enabled: false

  caido:
=======
  impacket:
    enabled: false

  bloodhound:
    enabled: false
    api_url: "http://127.0.0.1:8080"
    api_key: null

  caido:
>>>>>>> REPLACE

### Step 2 - Add implementation

WRITE src/kestrel_mcp/tools/bloodhound_tool.py

### Step 3 - Register module

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .caido_tool import CaidoModule
    from .engagement_tool import EngagementModule
=======
    from .bloodhound_tool import BloodHoundModule
    from .caido_tool import CaidoModule
    from .engagement_tool import EngagementModule
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        ImpacketModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
=======
        ImpacketModule(settings, scope_guard),
        BloodHoundModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
>>>>>>> REPLACE

### Step 4 - Add tests

WRITE tests/unit/tools/test_bloodhound_tool.py

### Step 5 - Update docs and trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-G08 — BloodHound-CE REST client

- **Mission**: 从 BloodHound-CE 容器拉取 AD 图分析结果
- **Binary**: docker-compose (用户自己起)
- **Budget**: 5 files

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-G08 | BloodHound-CE REST client         | open   |             |       |
=======
| RFC-G08 | BloodHound-CE REST client         | done   |             | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

APPEND TOOLS_MATRIX.md

### Step 6 - Verify

RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_bloodhound_tool.py -q

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- Query happy path sends cypher and engagement id.
- Dataset list happy path parses response JSON.
- HTTP error returns `ToolResult.is_error`.
- Registry loading is verified with `tools.bloodhound.enabled=true`.

## Post-checks

- `BloodHoundModule` loads when enabled.
- Default config keeps `tools.bloodhound.enabled` false.
- No Docker or network access is needed in tests.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove RFC-G08 stub.
- Mark RFC-G08 done in INDEX.
- Add changelog and TOOLS_MATRIX notes.

## Notes for executor

- BloodHound-CE API shape may vary by version; keep wrapper intentionally thin.
- Do not require a live container in tests.
- API key is config-supplied and must only be sent in Authorization header.

## Changelog

- **2026-04-21** - Executed: added opt-in BloodHound-CE REST client, tests,
  registry wiring, config defaults, and docs.
- **2026-04-21** - Expanded from Epic G stub for execution.
