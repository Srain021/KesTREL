---
id: RFC-G02
title: httpx probe tool
epic: G-Tool-expansion
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-G01]
edition: both
budget:
  max_files_touched: 10
  max_new_files: 2
  max_lines_added: 300
  max_minutes_human: 45
  max_tokens_model: 12000
files_to_read:
  - src/kestrel_mcp/tools/subfinder_tool.py
  - src/kestrel_mcp/tools/nuclei_tool.py
  - src/kestrel_mcp/tools/__init__.py
  - src/kestrel_mcp/config.py
  - src/kestrel_mcp/executor.py
  - config/default.yaml
files_will_touch:
  - rfcs/RFC-G02-httpx-probe-tool.md        # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - TOOLS_MATRIX.md                         # modified
  - src/kestrel_mcp/config.py               # modified
  - config/default.yaml                     # modified
  - src/kestrel_mcp/tools/__init__.py       # modified
  - src/kestrel_mcp/tools/httpx_tool.py     # new
  - tests/unit/tools/test_httpx_tool.py     # new
  - tests/test_tools_dispatch.py            # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/tools/test_httpx_tool.py tests/test_tools_dispatch.py -q
rollback_cmd: git checkout -- .
skill_id: rfc-g02-httpx-probe-tool
---

# RFC-G02 - httpx probe tool

## Mission

Add ProjectDiscovery httpx support for live HTTP probing.

## Context

- G01 returns hostnames; httpx turns them into live HTTP targets.
- The binary name collides with the Python `httpx` library, so this RFC treats
  `httpx` strictly as an external executable configured under `tools.httpx`.
- CI must mock subprocess execution and not require the binary.

## Non-goals

- Do not add a Python dependency; the implementation does not import `httpx`.
- Do not persist probe results into the engagement DB in this RFC.
- Do not install ProjectDiscovery httpx.

## Design

Create `HttpxModule` with:

- `httpx_probe(targets, tech_detect=True, status_code=True, title=True)`
- `httpx_version()`

Each target is checked against scope before execution. Targets are sent through
stdin and JSONL output is parsed into `{target, url, status_code, title, tech}`.

## Steps

### Step 1 - Add config field

REPLACE src/kestrel_mcp/config.py
<<<<<<< SEARCH
class ToolsSettings(BaseModel):
    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    shodan: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    subfinder: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
=======
class ToolsSettings(BaseModel):
    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    shodan: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    subfinder: ToolBlock = Field(default_factory=ToolBlock)
    httpx: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
>>>>>>> REPLACE

### Step 2 - Add default config

REPLACE config/default.yaml
<<<<<<< SEARCH
  subfinder:
    enabled: false
    binary: null

  caido:
=======
  subfinder:
    enabled: false
    binary: null

  httpx:
    enabled: false
    binary: null

  caido:
>>>>>>> REPLACE

### Step 3 - Add implementation

WRITE src/kestrel_mcp/tools/httpx_tool.py

### Step 4 - Register module

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .ligolo_tool import LigoloModule
    from .nuclei_tool import NucleiModule
=======
    from .httpx_tool import HttpxModule
    from .ligolo_tool import LigoloModule
    from .nuclei_tool import NucleiModule
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        NucleiModule(settings, scope_guard),
        SubfinderModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
=======
        NucleiModule(settings, scope_guard),
        SubfinderModule(settings, scope_guard),
        HttpxModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
>>>>>>> REPLACE

### Step 5 - Add tests and registry expectation

WRITE tests/unit/tools/test_httpx_tool.py

REPLACE tests/test_tools_dispatch.py
<<<<<<< SEARCH
                "subfinder",
                "caido",
=======
                "subfinder",
                "httpx",
                "caido",
>>>>>>> REPLACE

### Step 6 - Update docs and trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-G02 — httpx probe tool

- **Mission**: `httpx_probe(targets, tech_detect, status_code)`
- **Binary**: projectdiscovery/httpx
- **Blocking**: RFC-G01（顺序，不 hard 依赖）
- **Budget**: 3 files, 280 lines

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-G02 | httpx probe tool                  | open   | RFC-G01     |       |
=======
| RFC-G02 | httpx probe tool                  | done   | RFC-G01     | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

APPEND TOOLS_MATRIX.md

### Step 7 - Verify

RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_httpx_tool.py tests/test_tools_dispatch.py -q

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- Happy path parses JSONL probe records.
- Missing binary returns a `ToolResult.error`.
- Out-of-scope target raises `AuthorizationError`.
- Version handler invokes the configured binary.

## Post-checks

- `HttpxModule` appears when all tools are enabled.
- Default config keeps `tools.httpx.enabled` false.
- No Python `httpx` dependency/import is added.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove the RFC-G02 stub from `RFC-STUBS-B-D-E-F-G-H.md`.
- Mark RFC-G02 done in `rfcs/INDEX.md`.
- Add changelog and TOOLS_MATRIX notes.

## Notes for executor

- `httpx` here is a Go binary, not the Python package already used elsewhere.
- Feed targets via stdin so large lists do not require temp files.
- Scope-check every target before launching the binary.
- Tests must mock `run_command`; CI must not need httpx installed.

## Changelog

- **2026-04-21** - Executed: added opt-in httpx tool wrapper, tests,
  registry wiring, config defaults, and docs.
- **2026-04-21** - Expanded from Epic G stub for execution.
