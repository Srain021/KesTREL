---
id: RFC-B07a
title: Offensive readiness scoring engine
epic: B-CoreHardening
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-003b]
edition: both
budget:
  max_files_touched: 6
  max_new_files: 4
  max_lines_added: 400
  max_minutes_human: 45
  max_tokens_model: 22000
files_to_read:
  - src/kestrel_mcp/domain/entities.py
  - src/kestrel_mcp/domain/services/finding_service.py
  - src/kestrel_mcp/workflows/report.py
files_will_touch:
  - rfcs/RFC-B07a-offensive-readiness-scoring.md # new
  - src/kestrel_mcp/analysis/__init__.py # new
  - src/kestrel_mcp/analysis/readiness.py # new
  - tests/unit/analysis/test_readiness.py # new
  - rfcs/INDEX.md
  - CHANGELOG.md
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/analysis/test_readiness.py -q
rollback_cmd: |
  git checkout -- rfcs/INDEX.md CHANGELOG.md
  if exist src\kestrel_mcp\analysis\readiness.py del src\kestrel_mcp\analysis\readiness.py
  if exist src\kestrel_mcp\analysis\__init__.py del src\kestrel_mcp\analysis\__init__.py
  if exist tests\unit\analysis\test_readiness.py del tests\unit\analysis\test_readiness.py
  if exist rfcs\RFC-B07a-offensive-readiness-scoring.md del rfcs\RFC-B07a-offensive-readiness-scoring.md
skill_id: rfc-b07a-offensive-readiness-scoring
---

# RFC-B07a - Offensive readiness scoring engine

## Mission

Add a local scoring engine that turns findings into operator-ready triage.

## Context

Kestrel already discovers findings and stores CVE, CWE, CVSS, references, and
evidence. The missing layer is a deterministic "readiness" brain that tells an
operator whether a finding is parked, needs investigation, is ready to validate,
or needs human operator review before any high-risk action.

## Non-goals

- No exploit execution.
- No payload generation.
- No network access or external CVE lookups.
- No database migration.
- No MCP tool surface; that comes in RFC-B07c.

## Design

Create `kestrel_mcp.analysis.readiness` as a pure-Python engine. It accepts a
domain `Finding` object or a mapping plus optional enrichment/context mappings.
It emits a `ReadinessAssessment` containing score, rating, confidence, evidence
gaps, recommended next steps, safety gates, and transparent scoring signals.

The score intentionally favors evidence and known exploitation signals over raw
CVSS alone. High scores never execute anything; they only route the operator to
manual review and fire-control packaging in a future RFC.

## Steps

### Step 1 - Add scoring module

```
WRITE src/kestrel_mcp/analysis/__init__.py
```

```
WRITE src/kestrel_mcp/analysis/readiness.py
```

### Step 2 - Add tests

```
WRITE tests/unit/analysis/test_readiness.py
```

### Step 3 - Update trackers

```
APPEND CHANGELOG.md
```

```
REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-B06 | Tool degradation on missing binary| open   |             |       |
=======
| RFC-B06 | Tool degradation on missing binary| open   |             |       |
| RFC-B07a | Offensive readiness scoring      | open   | RFC-003b    |       |
>>>>>>> REPLACE
```

### Step 4 - Verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/analysis/test_readiness.py -q
```

## Tests

- CVE + KEV + high EPSS produces operator-review readiness.
- Unverified medium finding stays investigation-only and lists evidence gaps.
- Verified critical finding without a CVE becomes a zero-day hypothesis candidate.
- Domain `Finding` enum values normalize correctly.

## Notes for executor

- Keep the module side-effect-free and network-free.
- Do not include exploit commands, payload strings, or bypass guidance.
- Recommendations must be validation, evidence, and operator-review oriented.

## Changelog

- 2026-04-22 - Initial spec.
