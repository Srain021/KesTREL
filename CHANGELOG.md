# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

RFC-driven changes are tagged with their RFC id (e.g. `RFC-007: Web UI skeleton`).
See [`rfcs/INDEX.md`](./rfcs/INDEX.md) for the authoritative RFC tracker.

## [Unreleased]

### Added
- `RFC-T00b` - Consumed Team runtime feature gates: documented existing
  rate-limit bypass coverage and wired `credential_encryption_required` into
  `CredentialService`, `ServiceContainer`, and server startup.
- `RFC-003b` - Wired `CredentialService` into `ServiceContainer` and
  `RequestContext`, closed the split RFC-003 umbrella, and updated release
  security docs for encrypted-at-rest credentials.
- `RFC-003a` - Added encrypted credential seal/unseal domain service,
  Fernet key resolution, direct `cryptography` dependency, and unit tests.

## [1.0.0] - 2026-04-21

### Added
- `RFC-H04` - Finalized the v1.0.0 release gate with consistent package,
  server, shipped config, and lockfile version metadata plus a release checklist.
- `RFC-H03` - Added a lightweight MkDocs Material documentation site,
  GitHub Pages workflow, docs landing pages, and dev dependencies for local
  `mkdocs serve` preview.
- `RFC-H02` - Added tag-driven release infrastructure: PyPI trusted
  publishing, GHCR Docker image publishing, GitHub Release creation, a
  production Dockerfile, `.dockerignore`, and `docs/releasing.md`.
- `RFC-G08` - Added an opt-in BloodHound-CE REST client with
  `bloodhound_query`, `bloodhound_list_datasets`, and `bloodhound_version`,
  config defaults, bearer-token support, registry wiring, and mocked HTTP tests.
- `RFC-G06` - Added an opt-in Impacket wrapper for `psexec`, `smbexec`,
  `wmiexec`, `secretsdump`, and `GetUserSPNs`, with `impacket>=0.12` locked,
  scope enforcement, credential-redacted structured outputs, and mocked tests.
- `RFC-G04` - Added an opt-in ffuf wrapper with `ffuf_dir_bruteforce`,
  `ffuf_param_fuzz`, and `ffuf_version`, safe wordlist path handling, config
  defaults, registry wiring, and mocked subprocess tests.
- `RFC-G03` - Added an opt-in Nmap wrapper with `nmap_scan`,
  `nmap_os_detect`, and `nmap_version`, XML parsing, scope checks,
  `python-nmap` lockfile support, config defaults, registry wiring, and
  mocked subprocess tests.
- `RFC-G02` - Added an opt-in ProjectDiscovery `httpx` binary wrapper with
  `httpx_probe` and `httpx_version`, per-target scope checks, stdin-fed JSONL
  parsing, config defaults, registry wiring, and mocked subprocess tests.
- `RFC-G01` - Added an opt-in ProjectDiscovery `subfinder` wrapper with
  `subfinder_enum` and `subfinder_version`, JSONL parsing, scope enforcement,
  config defaults, registry wiring, and mocked subprocess tests.
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
- `RFC-H01` - Renamed the Python package and project identity from
  `redteam_mcp` / `redteam-mcp` to `kestrel_mcp` / `kestrel-mcp` in one
  atomic commit. This updates imports, tests, docs, RFC references, the CLI
  entry point (`kestrel`), env prefix (`KESTREL_MCP_`), user config dir
  (`~/.kestrel`), project config (`kestrel.yaml`), `pyproject.toml`,
  `uv.lock`, packaging manifests, Alembic path, and GitHub workflow refs.
- `RFC-002` - GitHub Actions CI is now checked in: lint (`ruff`), type checks
  (`mypy` on `core` + `domain`), 3 OS x 3 Python test matrix, weekly CodeQL,
  Dependabot, and a PR template. Team edition now has a real CI baseline.
- `scripts/full_verify.py` now resolves `.venv` executables cross-platform, so
  the same end-to-end verification script runs on Linux, macOS, and Windows.
- `src/kestrel_mcp/core` + `src/kestrel_mcp/domain` are now green under
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
  Every SEARCH block now copied from real `src/kestrel_mcp/__main__.py` and
  `config.py`. Passes `validate_rfc.py`.
- Executed RFC-A04 v2.0: adds `src/kestrel_mcp/features.py` (FeatureFlags
  pydantic model, 6 flags), `src/kestrel_mcp/editions/{__init__,pro,team}.py`
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

### Validator bug fixes + RFC-007 spec alignment (post-RFC-006 follow-up)
- `scripts/validate_rfc.py`: status=done / abandoned RFCs are now skipped for
  all content checks (C2-C10), receiving only front-matter sanity (C1, C9).
  Historical RFCs no longer flood reports with false C4/C6 errors.
- `scripts/validate_rfc.py`: force UTF-8 stdout/stderr on Windows so multi-RFC
  glob reports don't crash on cp936 encoding errors when a near-miss hint
  contains CJK.
- `rfcs/RFC-007-htmx-base-layout.md` Step 6 SEARCH: `async def root():` →
  `async def root() -> dict[str, object]:` to match real `webui/app.py` after
  agent added the return annotation during RFC-006 execution (for mypy --strict).
  RFC-007 now PASS preflight.
- `RFC_AUDIT_PREFLIGHT.md` v1.1: re-swept all 15 full-fleshed RFCs. Now
  **10 pass / 5 fail** (was 5 pass / 10 fail).

### RFC-T08 completed — Team MVP complete
- RFC-T08 v2.0 rewritten after v1 failed pre-flight (3 SEARCH hallucinations,
  1 WRITE-not-in-fwt, wrong `EngagementService.create` signature, wrong
  `ServiceContainer.default_on_disk` signature).
- Executed RFC-T08 v2.0: adds `src/kestrel_mcp/team/__init__.py`,
  `src/kestrel_mcp/team/bootstrap.py` (~130 LOC), `team` subcommand group in
  CLI with `bootstrap --name <slug> [--scope ...] [--dry-run]`, 6 new tests
  (including a real I/O test that builds an on-disk SQLite + Engagement).
- README: new "Team Edition Quickstart" section.
- Manual smoke test succeeded: dry-run produces a formatted report with
  banner, engagement details, doctor warnings (nuclei/sliver/caido/SHODAN
  missing), and next-steps.
- **Team MVP three-piece set (A04 + T00 + T08) now all `done`.**
- `full_verify.py` 8/8 (119 tests now, was 113).

### RFC-004 completed
- Executed RFC-004: added `src/kestrel_mcp/core/rate_limit.py` with an
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
  the FastAPI skeleton: `kestrel_mcp.webui.create_app(container)` now exposes
  `/` and `/api/v1/engagements` over a shared `ServiceContainer`.
- Added request middleware that opens a fresh `RequestContext` per HTTP request
  and attaches it to `request.state.ctx`, plus a small dependency helper for
  route injection.
- Added `fastapi` and `uvicorn[standard]` direct dependencies and refreshed
  `uv.lock`; 4 WebUI smoke tests cover health, docs, empty engagement lists,
  and persisted engagement listing.

### RFC-007 completed
- Executed RFC-007: `/` now renders a Jinja dashboard using the shared
  FastAPI `ServiceContainer` context instead of returning JSON.
- Added the base Web UI template set (`base`, nav partial, dashboard) with
  htmx, Alpine, and Tailwind CDN hooks and a reusable `templating.py` helper.
- Added `/__healthz` for the JSON health check and 3 HTML smoke tests; updated
  the RFC-006 root smoke test for the new HTML behavior.
- `full_verify.py` remains 8/8 green (154 tests now, was 151).

### RFC-008 completed
- Executed RFC-008: added `/engagements`, `/engagements/{slug}`, and htmx
  create flows backed by the shared `RequestContext` and `EngagementService`.
- Added the engagements route package, list/detail templates, reusable table
  row partial, and 5 route tests covering empty list, create, duplicate 409,
  detail page, and missing engagement 404.
- `full_verify.py` remains 8/8 green (159 tests now, was 154).

### RFC-009 completed
- Executed RFC-009: added `/engagements/{slug}/findings` with severity/status
  filtering and htmx row-level status transitions.
- Added findings table and row templates plus 5 route tests covering list,
  severity filtering, successful transition, invalid transition 409, and
  missing engagement 404.
- `full_verify.py` remains 8/8 green (164 tests now, was 159).

### RFC-011 completed
- Executed RFC-011: added a read-only `/settings` page showing runtime
  environment, authorized scope summary, config directory, and tool readiness.
- Reused existing doctor readiness helpers for binary/status checks while
  masking `SHODAN_API_KEY` as present/missing only.
- Added 3 route tests covering page render, environment labels, and secret
  masking.
- `full_verify.py` remains 8/8 green (167 tests now, was 164).

### RFC-012 completed
- Executed RFC-012: added optional app-wide HTTP Basic auth for the FastAPI
  Web UI, disabled by default and enabled via `Settings.webui.auth_required`.
- Credentials are read lazily from `KESTREL_WEB_USER`, `KESTREL_WEB_PASS`, or
  `KESTREL_WEB_TOKEN`; comparisons use `secrets.compare_digest`.
- Added `WebUISettings` config and 6 auth tests covering protected routes,
  valid/invalid credentials, and the default anonymous local mode.
- `full_verify.py` remains 8/8 green (173 tests now, was 167).

### RFC-010 split
- Superseded oversized RFC-010 with RFC-010a (backend jobs + JSON routes) and
  RFC-010b (HTML launcher + SSE endpoint) so each executable RFC stays under
  the hard 400-line budget.

### RFC-010a completed
- Executed RFC-010a: added an in-memory `JobRunner`, JSON `/tools` listing,
  `/tools/run`, and `/tools/jobs/{id}` backend routes.
- Tool execution uses injected `ToolSpec` handlers and a captured
  `RequestContext`, avoiding dependency on `RedTeamMCPServer`.
- Added 4 backend tests covering tool listing, job completion, bad JSON, and
  missing job 404.
- `full_verify.py` remains 8/8 green (177 tests now, was 173).

### RFC-010b completed
- Executed RFC-010b: added the `/tools` HTML launcher, htmx job-row partial,
  and `/tools/jobs/{id}/stream` SSE endpoint.
- Preserved RFC-010a's JSON behavior for `Accept: application/json` clients.
- Added 3 UI/SSE tests covering launcher render, htmx row response, and done
  event streaming.
- `full_verify.py` remains 8/8 green (180 tests now, was 177).

### Infrastructure
- Project is now tracked in git on branch `main`.
- `AGENT_EXECUTION_PROTOCOL.md` §6 whitelisted git commands are now functional.

## [0.1.0] — 2026-04-21 (pre-git baseline)

Prior state, now captured as the initial commit.

### Already delivered (prior to git init)
- Core package `kestrel_mcp` with 62 Python files, 21 modules.
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

### Tool guidance hardening — Impacket (RFC-B05a)
- `src/kestrel_mcp/tools/impacket_tool.py`:
  - `_credential_schema()` — every param now carries a `description`
    (closes the 28 missing-param-description gap peer flagged for Impacket).
  - `_exec_spec()` helper accepts per-tool `when_to_use`, `when_not_to_use`,
    `follow_ups`, `transport_hint`, `pitfalls_extra`, `local_hint`, `example`
    kwargs.
  - `psexec`, `smbexec`, `wmiexec` — each ships distinct guidance covering
    transport, stealth tradeoffs, event-log footprint, follow-up playbook.
  - `secretsdump`, `get_user_spns` — inline full guidance blocks including
    krbtgt-sensitivity warning, Kerberoast mode requirements, offline-crack
    follow-ups.
- `tests/unit/tools/test_impacket_tool.py`:
  - New `test_impacket_tools_have_complete_guidance` regression guard;
    any future Impacket spec without full guidance fails pytest.
- `scripts/validate_rfc.py` (small bug fix): C4 now exempts the RFC's own
  .md file (`rfcs/<rfc_id>-*.md`) which is listed `# new` in
  files_will_touch but already exists at preflight time.
- First phase of the B05 series (tool guidance completeness). Follow-ups:
  B05b (Sliver), B05c (Havoc+Evilginx), B05d (Ligolo+Caido), B05e
  (Engagement+Workflow), B05f (Epic G gaps + cross-module param sweep).

### Tool guidance hardening — Sliver server + run_command (RFC-B05b1)
- `src/kestrel_mcp/tools/sliver_tool.py`:
  - `sliver_start_server` (dangerous): full guidance covering 30s first-run
    cert init, gRPC port 31337 collision, ~/.sliver persistence, per-operator
    config + listener registration follow-ups, stealth/shutdown pitfalls,
    example start-then-poll conversation.
  - `sliver_stop_server`: session-kill-no-grace warning, PID-file semantics,
    Windows CTRL_BREAK caveat, "only stops MCP-started servers" clarifier.
  - `sliver_server_status`: cheap-call hint, PID-probe vs gRPC-responsive
    distinction, first-run polling guidance.
  - `sliver_run_command` (dangerous, power-user): escape-hatch guidance
    flagging "prefer dedicated tools" direction, audit-log 200-char truncation
    warning, parsed-table-vs-raw-stdout difference, armory/update timeout
    advice, example HTTPS listener registration.
  - Schema params `command`, `timeout_sec`, `daemon` gain proper descriptions.
- `tests/unit/tools/test_sliver_tool.py` (new, first Sliver test file):
  - 4 regression guard tests distinguishing dangerous (full guidance +
    example_conversation required) vs non-dangerous (core guidance) tools.
- Follow-up RFC-B05b2 will extend to the remaining 4 Sliver ops tools
  (list_sessions, list_listeners, generate_implant, execute_in_session).

### Tool guidance hardening - Sliver ops (RFC-B05b2)
- `src/kestrel_mcp/tools/sliver_tool.py`:
  - `sliver_list_sessions`: now framed as the mandatory gate before any
    session-scoped action, with stale-session, multi-session, and raw-table
    parsing cautions.
  - `sliver_list_listeners`: now framed as the mandatory gate before implant
    generation, with listener/protocol/callback mismatch warnings.
  - `sliver_generate_implant` (dangerous): full guidance covering listener
    verification, callback scope, OS/arch/format selection, artifact tracking,
    beacon tradeoffs, and explicit no-default-evasion posture.
  - `sliver_execute_in_session` (dangerous): full guidance requiring a fresh
    session list, exact session selection, bounded benign validation commands,
    audit-log sensitivity, and retry-after-relist behavior.
  - Every schema property on the 4 ops tools now carries a `description`.
- `tests/unit/tools/test_sliver_tool.py`:
  - Regression guard now covers all 8 Sliver tools, not only the B05b1 subset.
  - Dangerous Sliver tools require all guidance fields plus examples; inventory
    tools require core routing guidance; all schema params require descriptions.
