---
id: RFC-G04
title: ffuf wrapper
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
  - src/kestrel_mcp/tools/httpx_tool.py
  - src/kestrel_mcp/core/paths.py
  - src/kestrel_mcp/tools/__init__.py
  - src/kestrel_mcp/config.py
  - src/kestrel_mcp/executor.py
  - config/default.yaml
files_will_touch:
  - rfcs/RFC-G04-ffuf-wrapper.md            # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - TOOLS_MATRIX.md                         # modified
  - src/kestrel_mcp/config.py               # modified
  - config/default.yaml                     # modified
  - src/kestrel_mcp/tools/__init__.py       # modified
  - src/kestrel_mcp/tools/ffuf_tool.py      # new
  - tests/unit/tools/test_ffuf_tool.py      # new
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/tools/test_ffuf_tool.py -q
rollback_cmd: git checkout -- .
skill_id: rfc-g04-ffuf-wrapper
---

# RFC-G04 - ffuf wrapper

## Mission

Add an opt-in ffuf wrapper for directory and parameter fuzzing.

## Context

- ffuf is a core web fuzzing tool after httpx identifies live targets.
- Wordlist paths are LLM/user supplied, so they must go through `safe_path()`.
- This RFC keeps global dispatch tests untouched and verifies registry loading
  in the new ffuf-specific test to stay within the 10-file cap.

## Non-goals

- Do not ship wordlists.
- Do not run real ffuf in CI.
- Do not implement vhost fuzzing yet.

## Design

Create `FfufModule` with:

- `ffuf_dir_bruteforce(url, wordlist, extensions="", threads=40)`
- `ffuf_param_fuzz(url, wordlist)`
- `ffuf_version()`

The config block supports `tools.ffuf.wordlists_dir`; user-provided wordlist
names are resolved with `safe_path(wordlists_dir, wordlist)`.

## Steps

### Step 1 - Allow extra tool config blocks

REPLACE src/kestrel_mcp/config.py
<<<<<<< SEARCH
class ToolsSettings(BaseModel):
    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
=======
class ToolsSettings(BaseModel):
    model_config = {"extra": "allow"}

    nuclei: ToolBlock = Field(default_factory=lambda: ToolBlock(enabled=True))
>>>>>>> REPLACE

### Step 2 - Add default config

REPLACE config/default.yaml
<<<<<<< SEARCH
  nmap:
    enabled: false
    binary: null

  caido:
=======
  nmap:
    enabled: false
    binary: null

  ffuf:
    enabled: false
    binary: null
    wordlists_dir: "."

  caido:
>>>>>>> REPLACE

### Step 3 - Add implementation

WRITE src/kestrel_mcp/tools/ffuf_tool.py

### Step 4 - Register module

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .evilginx_tool import EvilginxModule
    from .havoc_tool import HavocModule
=======
    from .evilginx_tool import EvilginxModule
    from .ffuf_tool import FfufModule
    from .havoc_tool import HavocModule
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        NmapModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
=======
        NmapModule(settings, scope_guard),
        FfufModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
>>>>>>> REPLACE

### Step 5 - Add tests

WRITE tests/unit/tools/test_ffuf_tool.py

### Step 6 - Update docs and trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-G04 — ffuf wrapper

- **Mission**: `ffuf_dir_bruteforce(url, wordlist)`、`ffuf_param_fuzz`
- **Binary**: ffuf/ffuf

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-G04 | ffuf wrapper                      | open   |             |       |
=======
| RFC-G04 | ffuf wrapper                      | done   |             | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

APPEND TOOLS_MATRIX.md

### Step 7 - Verify

RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_ffuf_tool.py -q

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- Directory fuzz happy path parses mocked JSON output.
- Missing binary returns `ToolResult.error`.
- Out-of-scope URL raises `AuthorizationError`.
- Wordlist traversal is refused through `safe_path()`.
- Registry loading is verified with `tools.ffuf.enabled=true`.

## Post-checks

- `FfufModule` loads when enabled.
- Default config keeps `tools.ffuf.enabled` false.
- Wordlist paths are rooted under `tools.ffuf.wordlists_dir`.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove the RFC-G04 stub from `RFC-STUBS-B-D-E-F-G-H.md`.
- Mark RFC-G04 done in `rfcs/INDEX.md`.
- Add changelog and TOOLS_MATRIX notes.

## Notes for executor

- Do not accept absolute wordlist paths; use `safe_path()` with configured root.
- ffuf native JSON output is a single JSON document with a `results` list.
- Tests must mock `run_command`; CI must not need ffuf installed.

## Changelog

- **2026-04-21** - Executed: added opt-in ffuf wrapper, tests, registry
  wiring, config defaults, safe wordlist path handling, and docs.
- **2026-04-21** - Expanded from Epic G stub for execution.
