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
- `scripts/validate_rfc.py` — pre-flight validator for RFCs. 10 checks
  (C1-C10) catch phantom paths, hallucinated SEARCH blocks, budget overruns,
  non-whitelisted RUN commands. Runs in <1s.
- `RFC_AUDIT_PREFLIGHT.md` — 2026-04-21 audit report: 10 out of 15
  full-fleshed RFCs fail pre-flight. Root-cause analysis, defect taxonomy,
  per-RFC verdict.
- `SPEC_AUTHORING_CHECKLIST.md` — 12-section checklist every spec author
  must tick before submitting an RFC. Prevents the 5 defect classes found
  in the 2026-04-21 audit.

### Changed
- `RFC-002` - GitHub Actions CI is now checked in: lint (`ruff`), type checks
  (`mypy` on `core` + `domain`), 3 OS x 3 Python test matrix, weekly CodeQL,
  Dependabot, and a PR template. Team edition now has a real CI baseline.
- `scripts/full_verify.py` now resolves `.venv` executables cross-platform, so
  the same end-to-end verification script runs on Linux, macOS, and Windows.
- `src/redteam_mcp/core` + `src/redteam_mcp/domain` are now green under
  `mypy --strict`, and `ruff check src tests` is back to zero for CI.
- `RFC-001` - dependencies are now locked with `uv.lock`; reproducible installs
  use `uv sync --frozen --all-extras`. Closes GAP G-E3.
- `AGENT_EXECUTION_PROTOCOL.md` §5.0 — **mandatory pre-flight step** added.
  Executors must run `scripts/validate_rfc.py` before Step 1 of any RFC.
  Exit non-zero = abort without attempting execution.
- `.cursor/skills-cursor/kestrel-mcp/exec/rfc/SKILL.md` Step 3 — added
  `validate_rfc.py` invocation. Refuse to execute on failure.
- `.cursor/skills-cursor/kestrel-mcp/audit/rfc/SKILL.md` Step 0 — added
  machine pre-flight as first step.

### Fixed (RFC-001)
- RFC-001 Step 2 no longer inserts `[tool.uv] default-groups = ["dev"]`
  into `pyproject.toml` — that field references PEP 735's
  `[dependency-groups]` table; project uses PEP 621's
  `[project.optional-dependencies]`. Two specs are incompatible.
- RFC-001 Step 4 changed to `uv sync --frozen --all-extras` so dev deps
  still install.
- RFC-001 `Notes for executor` documents the pitfall.
- Discovered when first real RFC execution attempt crashed on Step 4.

### Marked blocked (spec_failed_preflight)
- RFC-003, RFC-T00, RFC-T08, RFC-006, RFC-010 — per RFC_AUDIT_PREFLIGHT.md.
  Require spec rewrite before they can execute.
- RFC-007, RFC-008, RFC-009 — blocked transitively on RFC-006 being fixed.

### RFC-A04 completed
- RFC-A04 v2.0 rewritten after v1 failed pre-flight (2 SEARCH hallucinations).
  Every SEARCH block now copied from real `src/redteam_mcp/__main__.py` and
  `config.py`. Passes `validate_rfc.py`.
- Executed RFC-A04 v2.0: adds `src/redteam_mcp/features.py` (FeatureFlags
  pydantic model, 6 flags), `src/redteam_mcp/editions/{__init__,pro,team}.py`
  (preset dispatch), `Settings.edition` + `Settings.features` fields +
  `Settings.build()` classmethod, CLI `--edition pro|team` global option,
  `kestrel show-config` command. 10 new tests.
- `full_verify.py` now 8/8 green (95 -> 105 tests passed). Smoke-tested
  both editions' `show-config` output. Pro edition runtime behavior unchanged.

### RFC-T00 completed
- RFC-T00 v2.0 rewritten after v1 failed pre-flight (6 SEARCH hallucinations,
  1 files_will_touch gap, 1 missing dep). Scope collapsed to a single-method
  change in `server._check_scope` instead of the v1's attempt to modify 4
  files (security.py / scope_service.py / context.py / rate_limit.py).
- Executed RFC-T00 v2.0: `server.RedTeamMCPServer._check_scope` now reads
  `self.settings.features.scope_enforcement` and honors three states —
  `strict` (raise, Pro default), `warn_only` (log + allow, Team default),
  `off` (silent pass-through). 8 new tests using `MagicMock(spec=...)` to
  avoid the heavy full-server fixture.
- Rate-limit and credential-encryption feature gates moved to a future
  RFC-T00b (needs `core/rate_limit.py`, not yet created).
- `full_verify.py` still 8/8 (113 tests now, was 105).

### RFC-T08 completed — Team MVP complete
- RFC-T08 v2.0 rewritten after v1 failed pre-flight (3 SEARCH hallucinations,
  1 WRITE-not-in-fwt, wrong `EngagementService.create` signature, wrong
  `ServiceContainer.default_on_disk` signature).
- Executed RFC-T08 v2.0: adds `src/redteam_mcp/team/__init__.py`,
  `src/redteam_mcp/team/bootstrap.py` (~130 LOC), `team` subcommand group in
  CLI with `bootstrap --name <slug> [--scope ...] [--dry-run]`, 6 new tests
  (including a real I/O test that builds an on-disk SQLite + Engagement).
- README: new "Team Edition Quickstart" section.
- Manual smoke test succeeded: dry-run produces a formatted report with
  banner, engagement details, doctor warnings (nuclei/sliver/caido/SHODAN
  missing), and next-steps.
- **Team MVP three-piece set (A04 + T00 + T08) now all `done`.**
- `full_verify.py` 8/8 (119 tests now, was 113).

### RFC-004 completed
- Executed RFC-004: added `src/redteam_mcp/core/rate_limit.py` with an
  in-process token-bucket `RateLimiter`, `RateLimitSpec`, and
  `RateLimitedError` for 429-style refusal handling.
- `ToolSpec` now supports optional `rate_limit`, and
  `server.RedTeamMCPServer` consults the limiter before dispatch when
  `features.rate_limit_enabled` is on. Team edition continues to bypass this
  path by default (`rate_limit_enabled=false`); Pro keeps it enabled.
- Added 8 unit tests covering burst behavior, refill, per-key isolation, GC,
  concurrency, and the Team-vs-Pro feature-flag behavior.
- This lays the groundwork for concrete per-tool `rate_limit=` policies on
  high-cost tools; cross-process enforcement remains future work.
- `full_verify.py` remains 8/8 green (127 tests now, was 119).

### RFC-005 completed
- Executed RFC-005: added `safe_path()` with `PathTraversalError` for
  path traversal defence and a dependency-free `redact()` helper for common
  subprocess stderr secrets.
- `run_command()` now redacts stderr by default and exposes
  `redact_stderr=False` for tests or narrowly-scoped raw diagnostics.
- Added 20 tests covering path traversal rejection, safe normalization,
  token/key/hash/private-key redaction, idempotency, and executor stderr
  integration.

### RFC-006 completed
- Rewrote the stale RFC-006 spec against the real repo layout, then executed
  the FastAPI skeleton: `redteam_mcp.webui.create_app(container)` now exposes
  `/` and `/api/v1/engagements` over a shared `ServiceContainer`.
- Added request middleware that opens a fresh `RequestContext` per HTTP request
  and attaches it to `request.state.ctx`, plus a small dependency helper for
  route injection.
- Added `fastapi` and `uvicorn[standard]` direct dependencies and refreshed
  `uv.lock`; 4 WebUI smoke tests cover health, docs, empty engagement lists,
  and persisted engagement listing.

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
