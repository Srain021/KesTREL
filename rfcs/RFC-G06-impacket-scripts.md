---
id: RFC-G06
title: Impacket scripts top 5
epic: G-Tool-expansion
status: done
owner: agent
role: backend-engineer
blocking_on: []
edition: both
budget:
  max_files_touched: 10
  max_new_files: 2
  max_lines_added: 400
  max_minutes_human: 60
  max_tokens_model: 16000
files_to_read:
  - src/kestrel_mcp/tools/ffuf_tool.py
  - src/kestrel_mcp/tools/__init__.py
  - src/kestrel_mcp/executor.py
  - config/default.yaml
  - pyproject.toml
files_will_touch:
  - rfcs/RFC-G06-impacket-scripts.md        # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - TOOLS_MATRIX.md                         # modified
  - config/default.yaml                     # modified
  - src/kestrel_mcp/tools/__init__.py       # modified
  - src/kestrel_mcp/tools/impacket_tool.py  # new
  - tests/unit/tools/test_impacket_tool.py  # new
  - pyproject.toml                          # modified
  - uv.lock                                 # modified
verify_cmd: .venv\Scripts\python.exe -m pytest tests/unit/tools/test_impacket_tool.py -q
rollback_cmd: git checkout -- .
skill_id: rfc-g06-impacket-scripts
---

# RFC-G06 - Impacket scripts top 5

## Mission

Wrap the top five Impacket example scripts for AD tradecraft.

## Context

- Impacket is Python-distributed and invoked as `python -m impacket.examples.*`.
- RFC-003 credential service is still blocked, so this RFC accepts plaintext
  username/password inputs temporarily.
- The implementation must not echo full argv because it contains credentials.

## Non-goals

- Do not implement credential vault integration yet.
- Do not run real Impacket against a host in CI.
- Do not wrap every Impacket example script.

## Design

Add `ImpacketModule` with handlers for `psexec`, `smbexec`, `wmiexec`,
`secretsdump`, and `GetUserSPNs`. Every handler scope-checks `target`, builds
an Impacket identity string, calls the Python module, and returns output tails
without exposing the credential-bearing argv.

## Steps

### Step 1 - Add dependency

REPLACE pyproject.toml
<<<<<<< SEARCH
    "uvicorn[standard]>=0.32",
    "python-nmap>=0.7",
]
=======
    "uvicorn[standard]>=0.32",
    "python-nmap>=0.7",
    "impacket>=0.12",
]
>>>>>>> REPLACE

### Step 2 - Add default config

REPLACE config/default.yaml
<<<<<<< SEARCH
  ffuf:
    enabled: false
    binary: null
    wordlists_dir: "."

  caido:
=======
  ffuf:
    enabled: false
    binary: null
    wordlists_dir: "."

  impacket:
    enabled: false

  caido:
>>>>>>> REPLACE

### Step 3 - Add implementation

WRITE src/kestrel_mcp/tools/impacket_tool.py

### Step 4 - Register module

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .httpx_tool import HttpxModule
    from .ligolo_tool import LigoloModule
=======
    from .httpx_tool import HttpxModule
    from .impacket_tool import ImpacketModule
    from .ligolo_tool import LigoloModule
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        FfufModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
=======
        FfufModule(settings, scope_guard),
        ImpacketModule(settings, scope_guard),
        CaidoModule(settings, scope_guard),
>>>>>>> REPLACE

### Step 5 - Add tests

WRITE tests/unit/tools/test_impacket_tool.py

### Step 6 - Update docs and trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-G06 — Impacket scripts (top 5)

- **Mission**: 封装 `psexec.py`, `smbexec.py`, `wmiexec.py`, `secretsdump.py`, `GetUserSPNs.py`
- **Binary**: `python -m impacket.examples.<script>` (pip 依赖)
- **Budget**: 6 files

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-G06 | Impacket scripts (5 key ones)     | open   |             |       |
=======
| RFC-G06 | Impacket scripts (5 key ones)     | done   |             | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

APPEND TOOLS_MATRIX.md

### Step 7 - Refresh lockfile

RUN .venv\Scripts\python.exe -m uv lock

### Step 8 - Verify

RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_impacket_tool.py -q

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- Happy path verifies module invocation and output handling.
- Non-zero command exit returns `ToolResult.is_error`.
- Out-of-scope target raises `AuthorizationError`.
- Registry loading is verified with `tools.impacket.enabled=true`.

## Post-checks

- `uv.lock` contains `impacket`.
- Structured outputs do not include credential-bearing argv.
- Default config keeps `tools.impacket.enabled` false.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove the RFC-G06 stub from `RFC-STUBS-B-D-E-F-G-H.md`.
- Mark RFC-G06 done in `rfcs/INDEX.md`.
- Add changelog and TOOLS_MATRIX notes.

## Notes for executor

- Plaintext credential args are temporary until RFC-003 lands.
- Do not return full argv in structured output; it contains passwords.
- `GetUserSPNs` module name is case-sensitive.
- Tests must mock `run_command`; CI must not need a domain controller.

## Changelog

- **2026-04-21** - Executed: added opt-in Impacket wrappers, tests, registry
  wiring, config defaults, `impacket` dependency lock, and docs.
- **2026-04-21** - Expanded from Epic G stub for execution.
