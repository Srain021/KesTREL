---
id: RFC-G01
title: subfinder tool
epic: G-Tool-expansion
status: done
owner: agent
role: backend-engineer
blocking_on: []
edition: both
budget:
  max_files_touched: 10
  max_new_files: 2
  max_lines_added: 300
  max_minutes_human: 45
  max_tokens_model: 12000
files_to_read:
  - src/kestrel_mcp/tools/shodan_tool.py
  - src/kestrel_mcp/tools/nuclei_tool.py
  - src/kestrel_mcp/tools/base.py
  - src/kestrel_mcp/tools/__init__.py
  - src/kestrel_mcp/config.py
  - src/kestrel_mcp/executor.py
  - config/default.yaml
files_will_touch:
  - rfcs/RFC-G01-subfinder-tool.md          # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - TOOLS_MATRIX.md                         # modified
  - src/kestrel_mcp/config.py               # modified
  - config/default.yaml                     # modified
  - src/kestrel_mcp/tools/__init__.py       # modified
  - src/kestrel_mcp/tools/subfinder_tool.py # new
  - tests/unit/tools/test_subfinder_tool.py # new
  - tests/test_tools_dispatch.py            # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/tools/test_subfinder_tool.py tests/test_tools_dispatch.py -q
rollback_cmd: git checkout -- .
skill_id: rfc-g01-subfinder-tool
---

# RFC-G01 - subfinder tool

## Mission

Add ProjectDiscovery subfinder support for passive subdomain enumeration.

## Context

- Epic G expands Kestrel's external tool wrappers after the package rename.
- subfinder is the first warmup tool: small command surface, JSONL output, and
  the same binary-backed pattern as Nuclei.
- The tool is opt-in by default because it executes an external binary and
  may make outbound OSINT requests.

## Non-goals

- Do not install or vendor subfinder.
- Do not require the binary in CI.
- Do not persist discovered subdomains into the domain DB in this RFC.

## Design

Create `SubfinderModule` with two MCP tools:

- `subfinder_enum(domain, all_sources=False, silent=True, timeout_sec=300)`
- `subfinder_version()`

`subfinder_enum` enforces scope on `domain`, resolves the configured binary,
runs JSONL output mode, parses `host` records, and returns both a text summary
and structured subdomain list.

## Steps

### Step 1 - Add the tool config model field

REPLACE src/kestrel_mcp/config.py
<<<<<<< SEARCH
class ToolsSettings(BaseModel):
    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    shodan: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    caido: ToolBlock = Field(default_factory=ToolBlock)
    evilginx: ToolBlock = Field(default_factory=ToolBlock)
    sliver: ToolBlock = Field(default_factory=ToolBlock)
    havoc: ToolBlock = Field(default_factory=ToolBlock)
    ligolo: ToolBlock = Field(default_factory=ToolBlock)
=======
class ToolsSettings(BaseModel):
    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    shodan: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
    subfinder: ToolBlock = Field(default_factory=ToolBlock)
    caido: ToolBlock = Field(default_factory=ToolBlock)
    evilginx: ToolBlock = Field(default_factory=ToolBlock)
    sliver: ToolBlock = Field(default_factory=ToolBlock)
    havoc: ToolBlock = Field(default_factory=ToolBlock)
    ligolo: ToolBlock = Field(default_factory=ToolBlock)
>>>>>>> REPLACE

### Step 2 - Add default YAML config

REPLACE config/default.yaml
<<<<<<< SEARCH
  shodan:
    enabled: true
    api_key_env: "SHODAN_API_KEY"
    default_limit: 100

  caido:
=======
  shodan:
    enabled: true
    api_key_env: "SHODAN_API_KEY"
    default_limit: 100

  subfinder:
    enabled: false
    binary: null

  caido:
>>>>>>> REPLACE

### Step 3 - Add the tool module implementation

WRITE src/kestrel_mcp/tools/subfinder_tool.py

### Step 4 - Register the module

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .nuclei_tool import NucleiModule
    from .shodan_tool import ShodanModule
    from .sliver_tool import SliverModule
=======
    from .nuclei_tool import NucleiModule
    from .shodan_tool import ShodanModule
    from .sliver_tool import SliverModule
    from .subfinder_tool import SubfinderModule
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        ShodanModule(settings, scope_guard),
        NucleiModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
=======
        ShodanModule(settings, scope_guard),
        NucleiModule(settings, scope_guard),
        SubfinderModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
>>>>>>> REPLACE

### Step 5 - Add tests and registry expectation

WRITE tests/unit/tools/test_subfinder_tool.py

REPLACE tests/test_tools_dispatch.py
<<<<<<< SEARCH
                "nuclei",
                "caido",
=======
                "nuclei",
                "subfinder",
                "caido",
>>>>>>> REPLACE

### Step 6 - Update docs and trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-G01 — subfinder tool

- **Mission**: `subfinder_enum(domain, all_sources)` + `subfinder_version`
- **Binary**: projectdiscovery/subfinder
- **Budget**: 3 files, 300 lines
- **Tests**: mock subprocess + 1 real integration test（有 binary 时）

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-G01 | subfinder tool                    | open   |             |       |
=======
| RFC-G01 | subfinder tool                    | done   |             | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

APPEND TOOLS_MATRIX.md

### Step 7 - Verify

RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_subfinder_tool.py tests/test_tools_dispatch.py -q

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- `test_subfinder_enum_parses_jsonl` mocks successful subprocess output.
- `test_subfinder_enum_returns_error_when_binary_missing` checks missing binary
  returns a `ToolResult.error`.
- `test_subfinder_enum_refuses_out_of_scope_domain` verifies scope refusal.
- `test_subfinder_version_uses_binary` verifies the metadata tool.

## Post-checks

- `SubfinderModule` appears when all tools are enabled.
- Default config keeps `tools.subfinder.enabled` false.
- `subfinder` is documented in `TOOLS_MATRIX.md`.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove the RFC-G01 stub from `RFC-STUBS-B-D-E-F-G-H.md`.
- Mark RFC-G01 done in `rfcs/INDEX.md`.
- Add a changelog and tool matrix note.

## Notes for executor

- The binary is named `subfinder`; do not confuse it with a Python package.
- JSONL lines may contain malformed noise; parser must skip bad lines.
- Scope is enforced on the apex `domain` before launching the binary.
- Tests must mock `run_command`; CI must not need subfinder installed.

## Changelog

- **2026-04-21** - Executed: added opt-in subfinder tool wrapper, tests,
  registry wiring, config defaults, and docs.
- **2026-04-21** - Expanded from Epic G stub for execution.
