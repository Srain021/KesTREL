---
id: RFC-H01
title: Rename package to kestrel-mcp
epic: H-Release
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-002]
budget_override: true
budget:
  max_files_touched: 80
  max_new_files: 0
  max_lines_added: 800
  max_minutes_human: 60
  max_tokens_model: 50000
files_to_read:
  - pyproject.toml
  - scripts/full_verify.py
  - scripts/validate_rfc.py
  - scripts/install_skills.ps1
  - src/redteam_mcp/config.py
  - src/redteam_mcp/__main__.py
files_will_touch:
  - src/redteam_mcp                         # modified (git mv source)
  - src/kestrel_mcp                         # new path via git mv, no net new files
  - tests                                   # modified imports
  - scripts/full_verify.py                  # modified
  - scripts/validate_rfc.py                 # modified (budget override + rename refs)
  - scripts/install_skills.ps1              # modified if old refs remain
  - pyproject.toml                          # modified
  - uv.lock                                 # modified
  - .github                                 # modified if workflow refs exist
  - .cursor                                 # modified docs/skills refs
  - rfcs                                   # modified docs/spec refs
  - README.md                               # modified
  - CONTRIBUTING.md                         # modified
  - SECURITY.md                             # modified
  - CHANGELOG.md                            # modified
  - AUDIT.md                                # modified
  - AUDIT_V2.md                             # modified
  - PRODUCT_LINES.md                        # modified
  - SKILLS_INTEGRATION.md                   # modified
verify_cmd: .venv\Scripts\python.exe scripts\full_verify.py
rollback_cmd: git checkout -- .
skill_id: rfc-h01-rename-kestrel-mcp
---

# RFC-H01 - Rename package to kestrel-mcp

## Mission

Rename the project and Python package to `kestrel-mcp` / `kestrel_mcp`.

## Context

- The public product name is now `kestrel-mcp`; keeping the package as
  `redteam_mcp` creates permanent churn for future RFCs.
- Epic G will add new tool modules; doing H01 first prevents every new tool
  from being renamed a second time.
- This rename must land in one big-bang commit because partial commits break
  imports, console entry points, and docs.

## Non-goals

- Do not change runtime behavior besides names, import paths, CLI entry point,
  env prefix, and default config locations.
- Do not edit `.git/` metadata or git config.
- Do not rewrite historical commit messages.

## Design

Use `git mv` for `src/redteam_mcp` -> `src/kestrel_mcp`, then run a tracked-file
text migration over source, tests, scripts, docs, workflows, RFCs, and skills.
`pyproject.toml` is reviewed explicitly for project name, console entry point,
and Hatch package target.

Budget override: this RFC intentionally exceeds the standard 10-file / 400-line
cap. A package rename is irreducibly cross-cutting and must be atomic to avoid a
broken intermediate tree. `budget_override: true` is limited to this RFC.

## Steps

### Step 1 - Rename the source package

RUN git mv src/redteam_mcp src/kestrel_mcp

### Step 2 - Run the tracked-file text migration

Create a temporary helper `scripts/_rename_h01.py`, run it, then delete it
before commit. The helper must walk `git ls-files`, skip `.git`, `.venv`,
`uv.lock`, and `pyproject.toml`, and replace only these case-sensitive tokens:

- `redteam-mcp.yaml` -> `kestrel.yaml`
- `.redteam-mcp` -> `.kestrel`
- `REDTEAM_MCP_` -> `KESTREL_MCP_`
- `redteam_mcp` -> `kestrel_mcp`
- `redteam-mcp` -> `kestrel-mcp`

RUN .venv\Scripts\python.exe scripts\_rename_h01.py

### Step 3 - Update pyproject metadata

REPLACE pyproject.toml
<<<<<<< SEARCH
name = "redteam-mcp"
=======
name = "kestrel-mcp"
>>>>>>> REPLACE

REPLACE pyproject.toml
<<<<<<< SEARCH
redteam-mcp = "redteam_mcp.__main__:main"
=======
kestrel = "kestrel_mcp.__main__:main"
>>>>>>> REPLACE

REPLACE pyproject.toml
<<<<<<< SEARCH
packages = ["src/redteam_mcp"]
=======
packages = ["src/kestrel_mcp"]
>>>>>>> REPLACE

### Step 4 - Review CLI display name and verification script

Ensure `src/kestrel_mcp/__main__.py` uses Typer app name `kestrel`.
Ensure `scripts/full_verify.py` imports `kestrel_mcp`, uses `KESTREL_MCP_*`
environment variables, and invokes the CLI through `python -m kestrel_mcp`
rather than the old `redteam-mcp` console script.

### Step 5 - Refresh dependency lock

RUN .venv\Scripts\python.exe -m uv lock

### Step 6 - Verify the rename

RUN .venv\Scripts\python.exe scripts\full_verify.py

RUN .venv\Scripts\ruff.exe check src tests

RUN .venv\Scripts\mypy.exe --strict src/kestrel_mcp/core src/kestrel_mcp/domain src/kestrel_mcp/webui

RUN .venv\Scripts\python.exe -m kestrel_mcp version

RUN .venv\Scripts\python.exe -m kestrel_mcp --edition team show-config

### Step 7 - Update RFC tracker and changelog

Set this RFC status to `done`, mark RFC-H01 done in `rfcs/INDEX.md`, and add a
CHANGELOG entry describing the package, CLI, env prefix, and config path rename.

### Step 8 - Final sanity

RUN git status --short

The final post-commit sanity must report zero dirty files.

## Tests

- `scripts/full_verify.py` remains 8/8.
- `ruff check src tests` is clean.
- `mypy --strict src/kestrel_mcp/core src/kestrel_mcp/domain src/kestrel_mcp/webui` is clean.
- `python -m kestrel_mcp version` works.
- `python -m kestrel_mcp --edition team show-config` works.

## Post-checks

- [ ] No `src/redteam_mcp` directory remains.
- [ ] `src/kestrel_mcp` imports cleanly.
- [ ] `redteam_mcp` package refs are gone from source and tests.
- [ ] `REDTEAM_MCP_` env refs are gone from source and tests.
- [ ] `git status --short` is empty after commit.

## Rollback plan

Rollback to the pre-H01 HEAD with `git checkout -- .` before commit. If already
committed, revert the H01 commit as one unit; do not partially revert a rename.

## Updates to other docs

- `CHANGELOG.md` gets an `[Unreleased]` H01 entry.
- `rfcs/INDEX.md` marks RFC-H01 done.
- Docs, RFCs, skills, scripts, and workflows get package/CLI/env-name text
  replacements where they reference the old names.

## Notes for executor

- This is the only RFC with `budget_override: true`; do not generalize the
  exception.
- Coordinator approved the final 118-file touch set even though front-matter
  declared 80 files; the atomic package rename expanded through docs, skills,
  tests, lockfile, installer manifests, and RFC references by necessity.
- `redteam-mcp.yaml` must become `kestrel.yaml`, not `kestrel-mcp.yaml`.
- Keep `KESTREL_EDITION`, `KESTREL_ENGAGEMENT`, and `KESTREL_DATA_DIR` as-is.
- Delete `scripts/_rename_h01.py` before committing.

## Changelog

- **2026-04-21** - Executed Phase 1 big-bang rename: package, imports, CLI,
  environment prefix, config paths, docs, tests, lockfile, and packaging refs
  migrated to kestrel-mcp / kestrel_mcp.
- **2026-04-21** - Expanded from Epic H stub for Phase 1 rename.
