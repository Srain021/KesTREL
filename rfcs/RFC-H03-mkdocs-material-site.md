---
id: RFC-H03
title: MkDocs Material site
epic: H-Release
status: done
owner: agent
role: docs
blocking_on: [RFC-H01]
edition: both
budget:
  max_files_touched: 10
  max_new_files: 4
  max_lines_added: 360
  max_minutes_human: 45
  max_tokens_model: 12000
files_to_read:
  - README.md
  - .github/workflows/ci.yml
  - pyproject.toml
files_will_touch:
  - rfcs/RFC-H03-mkdocs-material-site.md    # modified
  - rfcs/RFC-STUBS-B-D-E-F-G-H.md           # modified
  - rfcs/INDEX.md                           # modified
  - CHANGELOG.md                            # modified
  - pyproject.toml                          # modified
  - uv.lock                                 # modified
  - mkdocs.yml                              # new
  - docs/index.md                           # new
  - docs/rfcs/index.md                      # new
  - .github/workflows/pages.yml             # new
verify_cmd: .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-H03-mkdocs-material-site.md
rollback_cmd: git checkout -- .
skill_id: rfc-h03-mkdocs-material-site
---

# RFC-H03 - MkDocs Material site

## Mission

Add a lightweight MkDocs Material documentation site and Pages workflow.

## Context

- H01 renamed the package to kestrel-mcp.
- H02 added release infrastructure and a `docs/` directory.
- A full docs reorganization is too large for this RFC, so this RFC keeps a
  lightweight site that links to canonical top-level docs.

## Non-goals

- Do not move or rewrite all top-level markdown files.
- Do not publish Pages during local execution.
- Do not change runtime code.

## Design

Add `mkdocs.yml`, `docs/index.md`, `docs/rfcs/index.md`, and a GitHub Pages
workflow. Add `mkdocs` and `mkdocs-material` to dev extras so local preview is
reproducible with `uv run mkdocs serve`.

## Steps

### Step 1 - Add docs dependencies

REPLACE pyproject.toml
<<<<<<< SEARCH
    "mypy>=1.10",
    "types-PyYAML",
]
=======
    "mypy>=1.10",
    "types-PyYAML",
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
]
>>>>>>> REPLACE

### Step 2 - Add MkDocs config and pages

WRITE mkdocs.yml

WRITE docs/index.md

WRITE docs/rfcs/index.md

### Step 3 - Add Pages workflow

WRITE .github/workflows/pages.yml

### Step 4 - Update trackers

REPLACE rfcs/RFC-STUBS-B-D-E-F-G-H.md
<<<<<<< SEARCH
### RFC-H03 — MkDocs Material site

- **Mission**: 搭 docs 站点；host 到 GitHub Pages。
- **Blocking**: RFC-H01
- **Budget**: 10 files, 大量 reorg

=======
>>>>>>> REPLACE

REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-H03 | MkDocs Material site              | open   | RFC-H01     |       |
=======
| RFC-H03 | MkDocs Material site              | done   | RFC-H01     | agent |
>>>>>>> REPLACE

APPEND CHANGELOG.md

### Step 5 - Refresh lockfile

RUN .venv\Scripts\python.exe -m uv lock

### Step 6 - Verify

RUN .venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-H03-mkdocs-material-site.md

RUN .venv\Scripts\python.exe scripts\full_verify.py

## Tests

- RFC validator passes.
- Existing full_verify remains 8/8.
- MkDocs dependencies resolve in `uv.lock`.

## Post-checks

- `mkdocs.yml` nav links to docs pages and top-level reference docs.
- Pages workflow builds with `uv run --no-sync mkdocs build --strict`.
- No top-level docs are moved.

## Rollback plan

Run `git checkout -- .` before commit.

## Updates to other docs

- Remove H03 stub.
- Mark H03 done in INDEX.
- Add CHANGELOG entry.

## Notes for executor

- Keep this lightweight; do not reorganize the entire markdown tree.
- `docs/releasing.md` already exists from H02 and should be linked.
- Pages workflow requires `pages: write` and `id-token: write`.

## Changelog

- **2026-04-21** - Executed: added lightweight MkDocs Material site, Pages
  workflow, docs landing pages, dev dependency lock, and trackers.
- **2026-04-21** - Expanded from Epic H stub for execution.
