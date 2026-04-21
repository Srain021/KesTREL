---
id: RFC-B07c
title: Offensive readiness MCP tools
epic: B-CoreHardening
status: done
owner: agent
role: backend-engineer
blocking_on: [RFC-B07b]
edition: both
budget:
  max_files_touched: 7
  max_new_files: 2
  max_lines_added: 400
  max_minutes_human: 60
  max_tokens_model: 26000
files_to_read:
  - src/kestrel_mcp/analysis/readiness.py
  - src/kestrel_mcp/analysis/cve_enrichment.py
  - src/kestrel_mcp/tools/base.py
  - src/kestrel_mcp/tools/__init__.py
  - tests/test_tools_dispatch.py
files_will_touch:
  - rfcs/RFC-B07c-readiness-mcp-tools.md # new
  - src/kestrel_mcp/tools/readiness_tool.py # new
  - src/kestrel_mcp/tools/__init__.py
  - tests/unit/tools/test_readiness_tool.py # new
  - tests/test_tools_dispatch.py
  - rfcs/INDEX.md
  - CHANGELOG.md
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/tools/test_readiness_tool.py tests/test_tools_dispatch.py -q
rollback_cmd: |
  git checkout -- src/kestrel_mcp/tools/__init__.py tests/test_tools_dispatch.py rfcs/INDEX.md CHANGELOG.md
  if exist src\kestrel_mcp\tools\readiness_tool.py del src\kestrel_mcp\tools\readiness_tool.py
  if exist tests\unit\tools\test_readiness_tool.py del tests\unit\tools\test_readiness_tool.py
  if exist rfcs\RFC-B07c-readiness-mcp-tools.md del rfcs\RFC-B07c-readiness-mcp-tools.md
skill_id: rfc-b07c-readiness-mcp-tools
---

# RFC-B07c - Offensive readiness MCP tools

## Mission

Expose the B07 readiness brain as safe MCP advisory tools.

## Context

RFC-B07a added deterministic readiness scoring. RFC-B07b added read-only EPSS
and CISA KEV enrichment. Operators now need MCP-callable tools that package
findings into triage, attack-path plans, fire-control packets, zero-day
hypotheses, and evidence packs without executing any offensive action.

## Non-goals

- No exploit execution.
- No payload generation.
- No post-exploitation command dispatch.
- No persistence to DB or artifact files.
- No UI work; Web UI cards come later.

## Design

Add `ReadinessModule` with five tools:

- `exploitability_triage`
- `attack_path_plan`
- `operator_fire_control`
- `zero_day_hypothesis`
- `evidence_pack`

All tools are advisory. They return structured plans/checklists and never call
external offensive binaries. Optional CVE enrichment is explicit and read-only.

## Steps

### Step 1 - Add readiness tool module

```
WRITE src/kestrel_mcp/tools/readiness_tool.py
```

### Step 2 - Register module

```
REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
    from .nuclei_tool import NucleiModule
    from .shodan_tool import ShodanModule
    from .sliver_tool import SliverModule
    from .subfinder_tool import SubfinderModule
=======
    from .nuclei_tool import NucleiModule
    from .readiness_tool import ReadinessModule
    from .shodan_tool import ShodanModule
    from .sliver_tool import SliverModule
    from .subfinder_tool import SubfinderModule
>>>>>>> REPLACE
```

```
REPLACE src/kestrel_mcp/tools/__init__.py
<<<<<<< SEARCH
        EngagementModule(settings, scope_guard),
        # External-tool-backed modules follow.
        ShodanModule(settings, scope_guard),
=======
        EngagementModule(settings, scope_guard),
        ReadinessModule(settings, scope_guard),
        # External-tool-backed modules follow.
        ShodanModule(settings, scope_guard),
>>>>>>> REPLACE
```

### Step 3 - Add tests

```
WRITE tests/unit/tools/test_readiness_tool.py
```

```
REPLACE tests/test_tools_dispatch.py
<<<<<<< SEARCH
                "engagement",  # Sprint 3: domain management module
                "shodan",
=======
                "engagement",  # Sprint 3: domain management module
                "readiness",
                "shodan",
>>>>>>> REPLACE
```

### Step 4 - Update trackers

```
APPEND CHANGELOG.md
```

```
REPLACE rfcs/INDEX.md
<<<<<<< SEARCH
| RFC-B07b | CVE enrichment client            | done   | RFC-B07a    | agent |
=======
| RFC-B07b | CVE enrichment client            | done   | RFC-B07a    | agent |
| RFC-B07c | Offensive readiness MCP tools    | open   | RFC-B07b    |       |
>>>>>>> REPLACE
```

### Step 5 - Verify

```
RUN .venv\Scripts\python.exe -m pytest tests/unit/tools/test_readiness_tool.py tests/test_tools_dispatch.py -q
```

## Tests

- Registry exposes all five readiness tools.
- Triage returns an operator-review assessment for a high-confidence finding.
- Attack-path plan orders findings by readiness score and recommends tools.
- Fire-control packet requires human approval and never executes.
- Zero-day hypothesis and evidence pack are structured advisory packages.

## Notes for executor

- Keep examples and outputs advisory, not exploit instructions.
- Any target fields are metadata only; tag tools as `helper`/`audit`.
- Optional CVE enrichment must be explicit because it uses network.

## Changelog

- 2026-04-22 - Initial spec.
