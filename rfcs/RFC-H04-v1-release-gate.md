---
id: RFC-H04
title: v1.0 release gate + announcement
epic: H-Release
status: done
owner: agent
role: release-engineer
blocking_on: [RFC-H01, RFC-H02, RFC-H03, RFC-G01, RFC-G02, RFC-G03, RFC-G04, RFC-G06, RFC-G08]
edition: both
budget:
  max_files_touched: 10
  max_new_files: 2
  max_lines_added: 260
  max_minutes_human: 30
  max_tokens_model: 8000
files_to_read:
  - pyproject.toml
  - src/kestrel_mcp/__init__.py
  - CHANGELOG.md
  - docs/releasing.md
files_will_touch:
  - rfcs/RFC-H04-v1-release-gate.md       # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md         # modified
  - rfcs/INDEX.md                         # modified
  - CHANGELOG.md                          # modified
  - docs/RELEASE_CHECKLIST.md             # new
  - pyproject.toml                        # modified
  - src/kestrel_mcp/__init__.py           # modified
  - src/kestrel_mcp/config.py             # modified
  - config/default.yaml                   # modified
  - uv.lock                               # modified
verify_cmd: .venv\Scripts\python.exe scripts\full_verify.py
rollback_cmd: git checkout -- .
skill_id: rfc-h04-v1-release-gate
---

# RFC-H04 - v1.0 release gate + announcement

## Mission

Finalize the local v1.0.0 release gate without creating the tag.

## Context

- H01 renamed the project to kestrel-mcp.
- H02 added release automation for PyPI, GHCR, and GitHub Releases.
- H03 added the documentation site and Pages workflow.
- The remaining release gate is to make metadata consistent, freeze the
  changelog section, and document the human checklist before tag creation.

## Non-goals

- Do not create or push the `v1.0.0` tag in this RFC commit.
- Do not publish to PyPI, GHCR, or GitHub Releases locally.
- Do not add new runtime behavior beyond version string updates.

## Design

Set project, package, server, shipped config, and lockfile version metadata to
`1.0.0`. Convert the current changelog body from `[Unreleased]` into
`[1.0.0] - 2026-04-21`, then leave a fresh empty `[Unreleased]` header for
future work. Add a release checklist that records the required post-commit tag
command.

## Steps

### Step 1 - Update version metadata

REPLACE pyproject.toml
<<<<<<< SEARCH
version = "0.1.0"
=======
version = "1.0.0"
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/__init__.py
<<<<<<< SEARCH
__version__ = "0.1.0"
=======
__version__ = "1.0.0"
>>>>>>> REPLACE

REPLACE src/kestrel_mcp/config.py
<<<<<<< SEARCH
    version: str = "0.1.0"
=======
    version: str = "1.0.0"
>>>>>>> REPLACE

REPLACE config/default.yaml
<<<<<<< SEARCH
  version: "0.1.0"
=======
  version: "1.0.0"
>>>>>>> REPLACE

### Step 2 - Finalize release notes and checklist

REPLACE CHANGELOG.md
<<<<<<< SEARCH
## [Unreleased]

### Added
- `RFC-H03` - Added a lightweight MkDocs Material documentation site,
=======
## [Unreleased]

## [1.0.0] - 2026-04-21

### Added
- `RFC-H04` - Finalized the v1.0.0 release gate with consistent package,
  server, shipped config, and lockfile version metadata plus a release checklist.
- `RFC-H03` - Added a lightweight MkDocs Material documentation site,
>>>>>>> REPLACE

WRITE docs/RELEASE_CHECKLIST.md

RUN .venv\Scripts\python.exe -m uv lock

### Step 3 - Update trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-H04 — v1.0 release gate + announcement

- **Mission**: 发 v1.0。含 release checklist。
- **Blocking**: 所有上面的

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-H04 | v1.0 release gate + announcement  | open   | all above   |       |
=======
| RFC-H04 | v1.0 release gate + announcement  | done   | all above   | agent |
>>>>>>> REPLACE

### Step 4 - Verify

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-H04-v1-release-gate.md

RUN .venv\Scripts\python.exe scripts\full_verify.py

RUN .venv\Scripts\ruff.exe check src/ tests/

RUN .venv\Scripts\mypy.exe --strict src/kestrel_mcp/core src/kestrel_mcp/domain src/kestrel_mcp/webui

RUN .venv\Scripts\python.exe -m kestrel_mcp version

## Tests

- RFC validator passes.
- Existing full_verify remains 8/8.
- `python -m kestrel_mcp version` prints `1.0.0`.

## Post-checks

- No git tag exists or is created by this RFC.
- `CHANGELOG.md` has a fresh empty `[Unreleased]` section and a dated
  `[1.0.0]` section.
- `docs/RELEASE_CHECKLIST.md` documents the post-commit tag command.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove H04 stub.
- Mark H04 done in INDEX.
- Finalize CHANGELOG for v1.0.0.
- Add `docs/RELEASE_CHECKLIST.md`.

## Notes for executor

- The annotated tag is intentionally a post-commit manual step:
  `git tag -a v1.0.0 -m "kestrel-mcp v1.0.0" && git push origin v1.0.0`.
- Keep changes to version strings and release documentation only.
- Do not start RFC-003, G05, G07, or any Epic B/D/E/F/V work.

## Changelog

- **2026-04-21** - Executed: finalized v1.0.0 version metadata, release
  checklist, changelog section, and trackers without creating the tag.
- **2026-04-21** - Expanded from Epic H stub for execution.
