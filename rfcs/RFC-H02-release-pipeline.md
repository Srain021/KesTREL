---
id: RFC-H02
title: PyPI and Docker release pipeline
epic: H-Release
status: done
owner: agent
role: integration
blocking_on: [RFC-H01, RFC-002]
edition: both
budget:
  max_files_touched: 8
  max_new_files: 4
  max_lines_added: 260
  max_minutes_human: 45
  max_tokens_model: 10000
files_to_read:
  - .github/workflows/ci.yml
  - pyproject.toml
  - README.md
files_will_touch:
  - rfcs/RFC-H02-release-pipeline.md        # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - .github/workflows/release.yml           # new
  - Dockerfile                              # new
  - .dockerignore                           # new
  - docs/releasing.md                       # new
verify_cmd: .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-H02-release-pipeline.md
rollback_cmd: git checkout -- .
skill_id: rfc-h02-release-pipeline
---

# RFC-H02 - PyPI and Docker release pipeline

## Mission

Add tag-driven PyPI, GHCR, and GitHub Release automation.

## Context

- H01 completed the package rename to `kestrel-mcp`.
- The project already uses uv and frozen lockfiles in CI.
- Releases should be operator-triggered by annotated tags, not by every push.

## Non-goals

- Do not publish a release during this RFC.
- Do not add runtime code.
- Do not require Docker to be available for local tests.

## Design

Add `.github/workflows/release.yml` for `v*.*.*` tags. The workflow builds
Python distributions, publishes to PyPI via trusted publishing, builds and
pushes a GHCR image, then creates a GitHub Release. Add a multi-stage
`Dockerfile`, `.dockerignore`, and `docs/releasing.md`.

## Steps

### Step 1 - Add release workflow

WRITE .github/workflows/release.yml

### Step 2 - Add container packaging

WRITE Dockerfile

WRITE .dockerignore

### Step 3 - Add release docs

WRITE docs/releasing.md

### Step 4 - Update trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-H02 — PyPI + Docker release pipeline

- **Mission**: `release.yml` GitHub Action：tag → PyPI + GHCR + GitHub Release changelog
- **Blocking**: RFC-H01, RFC-002
- **Budget**: 4 files
- **Steps**:
  1. `.github/workflows/release.yml`
  2. `Dockerfile`（distroless-like 或 python:slim）
  3. `docs/releasing.md`

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-H02 | PyPI + Docker release pipeline    | open   | RFC-H01,RFC-002 |   |
=======
| RFC-H02 | PyPI + Docker release pipeline    | done   | RFC-H01,RFC-002 | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

### Step 5 - Verify

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-H02-release-pipeline.md

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- RFC validator must pass for H02.
- Existing full_verify remains 8/8.
- Workflow is declarative and tested by GitHub when a tag is pushed.

## Post-checks

- Release workflow triggers only on `v*.*.*` tags.
- Dockerfile entrypoint is `kestrel`.
- Docs describe PyPI trusted publishing and GHCR permissions.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove H02 stub.
- Mark H02 done in INDEX.
- Add CHANGELOG entry.

## Notes for executor

- Do not push tags in this RFC.
- `id-token: write` is required for PyPI trusted publishing.
- GHCR image name is derived from `${{ github.repository }}`.

## Changelog

- **2026-04-21** - Executed: added tag-driven release workflow, Dockerfile,
  `.dockerignore`, release docs, and trackers.
- **2026-04-21** - Expanded from Epic H stub for execution.
