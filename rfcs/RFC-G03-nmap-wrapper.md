---
id: RFC-G03
title: nmap wrapper
epic: G-Tool-expansion
status: done
owner: agent
role: backend-engineer
blocking_on: []
edition: both
budget:
  max_files_touched: 10
  max_new_files: 2
  max_lines_added: 360
  max_minutes_human: 60
  max_tokens_model: 14000
files_to_read:
  - src/kestrel_mcp/tools/httpx_tool.py
  - src/kestrel_mcp/tools/nuclei_tool.py
  - src/kestrel_mcp/tools/__init__.py
  - src/kestrel_mcp/config.py
  - src/kestrel_mcp/executor.py
  - config/default.yaml
  - pyproject.toml
files_will_touch:
  - rfcs/RFC-G03-nmap-wrapper.md            # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - TOOLS_MATRIX.md                         # modified
  - src/kestrel_mcp/config.py               # modified
  - config/default.yaml                     # modified
  - src/kestrel_mcp/tools/__init__.py       # modified
  - src/kestrel_mcp/tools/nmap_tool.py      # new
  - tests/unit/tools/test_nmap_tool.py      # new
  - tests/test_tools_dispatch.py            # modified
  - pyproject.toml                          # modified
  - uv.lock                                 # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/tools/test_nmap_tool.py tests/test_tools_dispatch.py -q
rollback_cmd: git checkout -- .
skill_id: rfc-g03-nmap-wrapper
---

# RFC-G03 - nmap wrapper

## Mission

Add an opt-in Nmap wrapper for port scanning and OS detection.

## Context

- Nmap is the standard service-discovery tool for targets identified by recon.
- Windows users need Npcap for many scan modes; CI must mock subprocess output.
- The RFC adds `python-nmap>=0.7` to the lockfile for XML parsing support.

## Non-goals

- Do not install Nmap or Npcap.
- Do not run real scans in tests.
- Do not add NSE exploit automation beyond accepting script names.

## Design

Create `NmapModule` with `nmap_scan`, `nmap_os_detect`, and `nmap_version`.
Handlers scope-check targets, call the configured `nmap` binary with `-oX -`,
then parse XML into host/port/OS structures. XML parsing prefers
`python-nmap` when available and falls back to stdlib XML parsing so current
CI remains deterministic before dependency sync.

## Steps

### Step 1 - Add dependency

REPLACE pyproject.toml
<<<<<<< SEARCH
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
]
=======
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-nmap>=0.7",
]
>>>>>>> REPLACE

### Step 2 - Add config

REPLACE src/kestrel_mcp/config.py
<<<<<<< SEARCH
    subfinder: ToolBlock = Field(default_factory=ToolBlock)
    httpx: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
=======
    subfinder: ToolBlock = Field(default_factory=ToolBlock)
    httpx: ToolBlock = Field(default_factory=ToolBlock)
    nmap: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
>>>>>>> REPLACE

REPLACE config/default.yaml
<<<<<<< SEARCH
  httpx:
    enabled: false
    binary: null

  caido:
=======
  httpx:
    enabled: false
    binary: null

  nmap:
    enabled: false
    binary: null

  caido:
>>>>>>> REPLACE

### Step 3 - Add implementation

WRITE src/kestrel_mcp/tools/nmap_tool.py

### Step 4 - Register module

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .nuclei_tool import NucleiModule
    from .shodan_tool import ShodanModule
=======
    from .nmap_tool import NmapModule
    from .nuclei_tool import NucleiModule
    from .shodan_tool import ShodanModule
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        HttpxModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
=======
        HttpxModule(settings, scope_guard),
        NmapModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
>>>>>>> REPLACE

### Step 5 - Add tests and registry expectation

WRITE tests/unit/tools/test_nmap_tool.py

REPLACE tests/test_tools_dispatch.py
<<<<<<< SEARCH
                "httpx",
                "caido",
=======
                "httpx",
                "nmap",
                "caido",
>>>>>>> REPLACE

### Step 6 - Update docs and trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-G03 — nmap wrapper

- **Mission**: `nmap_scan(targets, ports, scripts)` + `nmap_os_detect`
- **Binary**: nmap
- **Notes**: 输出解析用 `python-nmap>=0.7` 依赖。Windows 需 npcap。

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-G03 | nmap wrapper                      | open   |             |       |
=======
| RFC-G03 | nmap wrapper                      | done   |             | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

APPEND TOOLS_MATRIX.md

### Step 7 - Refresh lockfile

RUN .venv\Scripts\python.exe -m uv lock

### Step 8 - Verify

RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_nmap_tool.py tests/test_tools_dispatch.py -q

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- Happy path parses mocked XML output.
- Missing binary returns `ToolResult.error`.
- Out-of-scope target raises `AuthorizationError`.
- OS detect and version handlers are smoke-tested with mocks.

## Post-checks

- `NmapModule` appears when all tools are enabled.
- Default config keeps `tools.nmap.enabled` false.
- `uv.lock` contains `python-nmap`.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove the RFC-G03 stub from `RFC-STUBS-B-D-E-F-G-H.md`.
- Mark RFC-G03 done in `rfcs/INDEX.md`.
- Add changelog and TOOLS_MATRIX notes.

## Notes for executor

- Windows operators need Npcap installed for common Nmap scan modes.
- Do not run real Nmap in CI; tests must mock `run_command`.
- `python-nmap` may be absent in the active venv until sync; keep XML parsing
  resilient with a stdlib fallback.
- `timing` maps to `-T<0-5>` and must be clamped in input schema.

## Changelog

- **2026-04-21** - Executed: added opt-in Nmap wrapper, tests, registry
  wiring, config defaults, `python-nmap` dependency lock, and docs.
- **2026-04-21** - Expanded from Epic G stub for execution.
