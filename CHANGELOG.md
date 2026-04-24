# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

RFC-driven changes are tagged with their RFC id (e.g. `RFC-007: Web UI skeleton`).
See [`rfcs/INDEX.md`](./rfcs/INDEX.md) for the authoritative RFC tracker.

## [Unreleased]

### Added
- Git baseline: initial `git init` + first commit establishing pre-RFC-001
  working tree.
- `CHANGELOG.md` — this file.
- `CONTRIBUTING.md` — contribution workflow and RFC protocol.
- `SECURITY.md` — vulnerability reporting policy.
- `.editorconfig` — cross-IDE style consistency.
- `scripts/sync_rfc_index.py` — scans `rfcs/RFC-*.md` front-matter, refreshes
  `rfcs/INDEX.md` status table. Previously promised but missing.

### Infrastructure
- Project is now tracked in git on branch `main`.
- `AGENT_EXECUTION_PROTOCOL.md` §6 whitelisted git commands are now functional.

## [0.1.0] — 2026-04-21 (pre-git baseline)

Prior state, now captured as the initial commit.

### Already delivered (prior to git init)
- Core package `redteam_mcp` with 62 Python files, 21 modules.
- 57 MCP tools across 9 modules (nuclei, sliver, caido, shodan, havoc, evilginx,
  ligolo, engagement, report).
- 95 unit tests, all passing; `scripts/full_verify.py` reports 8/8 checks green.
- FastAPI web UI skeleton with htmx + Alpine + Tailwind CDN base layout.
- SQLAlchemy 2.0 async domain model with 22 Pydantic entities and 9 services.
- Alembic migrations.
- Engagement/Scope/Target/Finding/Credential services.
- MCP server with structured context (`RequestContext` via `contextvars`).
- Rich `ToolSpec` descriptions (`when_to_use`, `pitfalls`, `local_model_hints`).
- RFC framework: 12 detailed RFCs + 28 stubs + template + index (63 total).
- Cursor skills: 15 skills across 7 categories + install script.
- Documentation: AUDIT (v1 + v2), PRODUCT_LINES, AGENT_EXECUTION_PROTOCOL,
  README_FOR_AGENT, SKILLS_INTEGRATION, CTF_ECOSYSTEM_RESEARCH.

### Known limitations at 0.1.0
- No CI (awaits RFC-002).
- No dependency lockfile (awaits RFC-001).
- No Pro/Team edition separation (awaits RFC-A04).
- No release pipeline (awaits RFC-H02).

See [AUDIT.md](./AUDIT.md) and [AUDIT_V2.md](./AUDIT_V2.md) for the full gap log.
