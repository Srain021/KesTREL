---
id: RFC-V14a
title: Add HARNESS adaptive small-model loop
epic: V-CrossEdition
status: open
owner: unassigned
role: backend-engineer
edition: both
blocking_on:
  - RFC-V13d
budget:
  max_files_touched: 6
  max_new_files: 1
  max_lines_added: 260
  max_minutes_human: 60
  max_tokens_model: 20000
files_to_read:
  - AUDIT_V2.md
  - rfcs/RFC-V13-HARNESS-local-model-runtime.md
  - rfcs/RFC-V13a-compact-tool-catalog.md
  - rfcs/RFC-V13c-harness-mcp-tools.md
  - src/kestrel_mcp/tools/base.py
  - src/kestrel_mcp/tool_catalog.py
  - src/kestrel_mcp/harness/planner.py
  - src/kestrel_mcp/harness/module.py
  - tests/unit/test_harness_planner.py
  - tests/unit/test_harness_module.py
files_will_touch:
  - rfcs/RFC-V14a-harness-adaptive-loop.md # new
  - src/kestrel_mcp/harness/planner.py # modified
  - src/kestrel_mcp/harness/module.py # modified
  - tests/unit/test_harness_planner.py # modified
  - tests/unit/test_harness_module.py # modified
  - CHANGELOG.md # modified
verify_cmd: |
  .venv\Scripts\python.exe -m pytest tests/unit/test_harness_planner.py tests/unit/test_harness_module.py -v
rollback_cmd: |
  git checkout -- src/kestrel_mcp/harness/planner.py src/kestrel_mcp/harness/module.py tests/unit/test_harness_planner.py tests/unit/test_harness_module.py CHANGELOG.md
  rm rfcs/RFC-V14a-harness-adaptive-loop.md
skill_id: rfc-v14a-harness-adaptive-loop
---

# RFC-V14a - Add HARNESS adaptive small-model loop

## Mission

Make HARNESS return one bounded next step with explicit model-tier routing.

## Context

- Closes AUDIT_V2 V-C1, V-C5, and V-A1 first-slice gaps: mixed-model routing, subtask guidance, and local-model capability limits.
- Extends RFC-V13/V13a/V13c/V13d, which added HARNESS sessions, compact catalog, and four public HARNESS MCP tools.
- Current `HarnessPlanner` is static: it emits a fixed recon order, has no local result budget, and can retry a failed tool because failed steps do not count as done.
- Tool inventory shows enough metadata already exists on `ToolSpec`: `dangerous`, `tags`, `complexity_tier`, and `preferred_model_tier`; V2 should consume this before adding new public tools.

## Non-goals

- Do not add external LLM provider calls or API keys.
- Do not add new public MCP tools; keep the external surface as `harness_start`, `harness_next`, `harness_run`, and `harness_state`.
- Do not change the HARNESS database schema in this RFC.
- Do not rewrite all tool metadata; this RFC only changes HARNESS policy usage.

## Design

HARNESS becomes the planner; the model becomes the executor. `harness_next` may create at most one runnable step. Local model steps must have fully bound tool arguments. Standard tier is recommended for broad results, repeated ambiguity, and vulnerability triage. Strong tier is recommended for high-risk tags such as `c2`, `exploit`, `post-ex`, `credentials`, and `phish`.

The MVP uses only data already persisted today: step status, tool name, reason, result summary, and `ToolSpec` metadata. Since RFC-V13 does not persist full structured tool output, this RFC parses count-like hints from `result_summary` and improves `_summarize_result` so common tools expose `count`, `findings_count`, `hosts`, `probes`, `results`, or `subdomains` as compact summaries.

## Steps

### Step 1 - Add HARNESS policy constants and constructor injection

```text
REPLACE src/kestrel_mcp/harness/planner.py
<<<<<<< SEARCH
@dataclass(frozen=True)
class PlannedStep:
    tool_name: str
    arguments: dict[str, object]
    risk_level: str
    recommended_model_tier: str
    reason: str

    @property
    def requires_confirmation(self) -> bool:
        return self.risk_level == "high"


class HarnessPlanner:
    def __init__(self, specs: dict[str, ToolSpec]) -> None:
        self._specs = specs
=======
@dataclass(frozen=True)
class HarnessPolicy:
    local_result_item_limit: int = 20
    broad_result_item_limit: int = 50
    max_failed_steps_before_strong: int = 2


@dataclass(frozen=True)
class PlannedStep:
    tool_name: str
    arguments: dict[str, object]
    risk_level: str
    recommended_model_tier: str
    reason: str

    @property
    def requires_confirmation(self) -> bool:
        return self.risk_level == "high"


class HarnessPlanner:
    def __init__(
        self,
        specs: dict[str, ToolSpec],
        *,
        policy: HarnessPolicy | None = None,
    ) -> None:
        self._specs = specs
        self._policy = policy or HarnessPolicy()
>>>>>>> REPLACE
```

### Step 2 - Replace static next-step routing with adaptive short-step routing

```text
REPLACE src/kestrel_mcp/harness/planner.py
<<<<<<< SEARCH
        done = {step.tool_name for step in steps if step.status == ent.HarnessStepStatus.DONE}
        target_type = classify_target(target)

        if "scope_check" not in done and "scope_check" in self._specs:
            return self._plan("scope_check", {"target": target}, "low", "Verify scope first.")

        if "target_add" not in done and "target_add" in self._specs:
            return self._plan(
                "target_add",
                {
                    "kind": target_kind_for_add(target_type),
                    "value": target,
                    "discovered_by_tool": "harness",
                },
                "low",
                "Persist the operator-provided target before scanning.",
            )

        if _has_large_result(steps) and "target_list" not in done and "target_list" in self._specs:
            return self._plan(
                "target_list",
                {},
                "low",
                "Recent results are broad; review targets and choose a narrower subset.",
            )

        if target_type == "domain" and "subfinder_enum" not in done and "subfinder_enum" in self._specs:
            return self._plan(
                "subfinder_enum",
                {"domain": strip_url(target), "silent": True},
                "medium",
                "Passive domain recon is the cheapest useful next step.",
            )

        if target_type == "ip" and "nmap_scan" not in done and "nmap_scan" in self._specs:
            return self._plan(
                "nmap_scan",
                {"targets": [target], "ports": "1-1024", "timing": 3},
                "medium",
                "Map common ports before choosing service-specific probes.",
            )

        if target_type in {"domain", "url", "ip"} and "httpx_probe" not in done and "httpx_probe" in self._specs:
            return self._plan(
                "httpx_probe",
                {"targets": [target], "tech_detect": True, "status_code": True, "title": True},
                "medium",
                "Confirm live HTTP services before vulnerability scanning.",
            )

        if "nuclei_scan" not in done and "nuclei_scan" in self._specs:
            scan_target = target if target.startswith(("http://", "https://")) else target
            return self._plan(
                "nuclei_scan",
                {"targets": [scan_target], "severity": ["critical", "high"]},
                "medium",
                "Run a narrow high-signal vulnerability baseline.",
            )

        return None
=======
        done = {step.tool_name for step in steps if step.status == ent.HarnessStepStatus.DONE}
        attempted = {step.tool_name for step in steps}
        failed_count = sum(1 for step in steps if step.status == ent.HarnessStepStatus.FAILED)
        target_type = classify_target(target)

        if failed_count and "target_list" in self._specs and "target_list" not in attempted:
            tier = "strong" if failed_count >= self._policy.max_failed_steps_before_strong else "standard"
            return self._plan(
                "target_list",
                {},
                "low",
                "Previous HARNESS step failed; inspect persisted targets before retrying.",
                recommended_model_tier=tier,
            )

        if "scope_check" not in attempted and "scope_check" in self._specs:
            return self._plan(
                "scope_check",
                {"target": target},
                "low",
                "Verify scope first.",
                recommended_model_tier="local",
            )

        if "target_add" not in attempted and "target_add" in self._specs:
            return self._plan(
                "target_add",
                {
                    "kind": target_kind_for_add(target_type),
                    "value": target,
                    "discovered_by_tool": "harness",
                },
                "low",
                "Persist the operator-provided target before scanning.",
                recommended_model_tier="local",
            )

        if _has_large_result(steps, self._policy) and "target_list" not in attempted and "target_list" in self._specs:
            return self._plan(
                "target_list",
                {},
                "low",
                "Recent results exceed the local-model fan-out budget; review targets and choose a narrower subset.",
                recommended_model_tier="standard",
            )

        if target_type == "domain" and "subfinder_enum" not in attempted and "subfinder_enum" in self._specs:
            return self._plan(
                "subfinder_enum",
                {"domain": strip_url(target), "silent": True},
                "medium",
                "Run one passive domain enumeration step.",
                recommended_model_tier="local",
            )

        if target_type == "ip" and "nmap_scan" not in attempted and "nmap_scan" in self._specs:
            return self._plan(
                "nmap_scan",
                {"targets": [target], "ports": "1-1024", "timing": 3},
                "medium",
                "Run one bounded TCP discovery step.",
                recommended_model_tier="local",
            )

        if target_type in {"domain", "url", "ip"} and "httpx_probe" not in attempted and "httpx_probe" in self._specs:
            return self._plan(
                "httpx_probe",
                {"targets": [target], "tech_detect": True, "status_code": True, "title": True},
                "medium",
                "Confirm one live HTTP surface before vulnerability scanning.",
                recommended_model_tier="local",
            )

        if "nuclei_scan" not in attempted and "nuclei_scan" in self._specs:
            scan_target = target if target.startswith(("http://", "https://")) else target
            return self._plan(
                "nuclei_scan",
                {"targets": [scan_target], "severity": ["critical", "high"]},
                "medium",
                "Run a narrow high-signal vulnerability baseline; standard tier should interpret findings.",
                recommended_model_tier="standard",
            )

        return None
>>>>>>> REPLACE
```

### Step 3 - Make model-tier selection explicit in `_plan`

```text
REPLACE src/kestrel_mcp/harness/planner.py
<<<<<<< SEARCH
    def _plan(
        self,
        tool_name: str,
        arguments: dict[str, object],
        risk_level: str,
        reason: str,
    ) -> PlannedStep:
        spec = self._specs[tool_name]
        if _is_high_risk(spec):
            risk_level = "high"
        return PlannedStep(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            recommended_model_tier=spec.preferred_model_tier,
            reason=reason,
        )
=======
    def _plan(
        self,
        tool_name: str,
        arguments: dict[str, object],
        risk_level: str,
        reason: str,
        *,
        recommended_model_tier: str | None = None,
    ) -> PlannedStep:
        spec = self._specs[tool_name]
        if _is_high_risk(spec):
            risk_level = "high"
        tier = recommended_model_tier or spec.preferred_model_tier
        if risk_level == "high":
            tier = "strong"
        return PlannedStep(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            recommended_model_tier=tier,
            reason=reason,
        )
>>>>>>> REPLACE
```

### Step 4 - Replace broad-result detection with policy-based result counting

```text
REPLACE src/kestrel_mcp/harness/planner.py
<<<<<<< SEARCH
def _has_large_result(steps: list[ent.HarnessStep]) -> bool:
    for step in reversed(steps):
        if step.status != ent.HarnessStepStatus.DONE or not step.result_summary:
            continue
        for key, threshold in {"count": 50, "findings_count": 20}.items():
            match = re.search(rf"\b{key}=(\d+)\b", step.result_summary)
            if match and int(match.group(1)) > threshold:
                return True
        return False
    return False
=======
def _has_large_result(steps: list[ent.HarnessStep], policy: HarnessPolicy) -> bool:
    for step in reversed(steps):
        if step.status != ent.HarnessStepStatus.DONE or not step.result_summary:
            continue
        count = _result_count(step.result_summary)
        if count is None:
            return False
        if "findings_count=" in step.result_summary:
            return count > policy.local_result_item_limit
        return count > policy.broad_result_item_limit
    return False


def _result_count(summary: str) -> int | None:
    for key in ("findings_count", "count", "hosts", "probes", "results", "subdomains"):
        match = re.search(rf"\b{key}=(\d+)\b", summary)
        if match:
            return int(match.group(1))
    return None
>>>>>>> REPLACE
```

### Step 5 - Summarize common structured results into planner-readable counts

```text
REPLACE src/kestrel_mcp/harness/module.py
<<<<<<< SEARCH
def _summarize_result(result: ToolResult) -> str:
    if result.structured and "count" in result.structured:
        return f"{result.text} count={result.structured['count']}"
    if result.structured and "findings_count" in result.structured:
        return f"{result.text} findings_count={result.structured['findings_count']}"
    return result.text[:4096]
=======
def _summarize_result(result: ToolResult) -> str:
    if not result.structured:
        return result.text[:4096]
    for key in ("findings_count", "count"):
        if key in result.structured:
            return f"{result.text} {key}={result.structured[key]}"
    for key in ("hosts", "probes", "results", "subdomains"):
        value = result.structured.get(key)
        if isinstance(value, list):
            return f"{result.text} {key}={len(value)}"
    return result.text[:4096]
>>>>>>> REPLACE
```

### Step 6 - Add planner tests for local, standard, and failure routing

```text
APPEND tests/unit/test_harness_planner.py


def test_setup_steps_are_local_even_when_specs_default_standard() -> None:
    planner = HarnessPlanner({"scope_check": _spec("scope_check")})
    session = _session("example.com")

    step = planner.next_step(session, [])

    assert step is not None
    assert step.tool_name == "scope_check"
    assert step.recommended_model_tier == "local"


def test_broad_result_recommends_standard_target_review() -> None:
    specs = {
        name: _spec(name)
        for name in ["scope_check", "target_add", "subfinder_enum", "target_list"]
    }
    planner = HarnessPlanner(specs)
    session = _session("example.com")

    step = planner.next_step(
        session,
        [
            _done(session.id, 1, "scope_check"),
            _done(session.id, 2, "target_add"),
            _done_with_summary(session.id, 3, "subfinder_enum", "found subdomains subdomains=75"),
        ],
    )

    assert step is not None
    assert step.tool_name == "target_list"
    assert step.recommended_model_tier == "standard"


def test_nuclei_baseline_recommends_standard_for_interpretation() -> None:
    specs = {
        name: _spec(name)
        for name in ["scope_check", "target_add", "httpx_probe", "nuclei_scan"]
    }
    planner = HarnessPlanner(specs)
    session = _session("https://app.example.com")

    step = planner.next_step(
        session,
        [
            _done(session.id, 1, "scope_check"),
            _done(session.id, 2, "target_add"),
            _done(session.id, 3, "httpx_probe"),
        ],
    )

    assert step is not None
    assert step.tool_name == "nuclei_scan"
    assert step.recommended_model_tier == "standard"


def test_failed_step_routes_to_standard_review_instead_of_retrying() -> None:
    specs = {
        name: _spec(name)
        for name in ["scope_check", "target_add", "subfinder_enum", "target_list"]
    }
    planner = HarnessPlanner(specs)
    session = _session("example.com")
    failed = _done_with_summary(session.id, 3, "subfinder_enum", "ERROR: binary missing")
    failed.status = ent.HarnessStepStatus.FAILED

    step = planner.next_step(
        session,
        [
            _done(session.id, 1, "scope_check"),
            _done(session.id, 2, "target_add"),
            failed,
        ],
    )

    assert step is not None
    assert step.tool_name == "target_list"
    assert step.recommended_model_tier == "standard"
```

### Step 7 - Add module test for planner-readable summaries

```text
APPEND tests/unit/test_harness_module.py


async def test_harness_summary_counts_common_structured_lists(container) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def runner(tool_name: str, arguments: dict[str, object]):
        calls.append((tool_name, arguments))
        return ToolResult(
            text="httpx identified 2 live HTTP service(s).",
            structured={"probes": [{"url": "https://a.test"}, {"url": "https://b.test"}]},
        ), None

    module = HarnessModule(
        Settings.build(),
        ScopeGuard([]),
        specs_provider=lambda: {},
        runner=runner,
    )

    async with container.open_context():
        session = await container.harness.create_session(
            goal="Probe",
            target="example.com",
            engagement_id=None,
            mode="recon",
            model_tier="local",
        )
        step = await container.harness.add_step(
            session_id=session.id,
            tool_name="httpx_probe",
            arguments={"targets": ["example.com"]},
            status=ent.HarnessStepStatus.PENDING,
            risk_level="medium",
            recommended_model_tier="local",
            reason="test",
        )

        result = await _spec(module, "harness_run").handler(
            {"session_id": str(session.id), "step_id": str(step.id)}
        )
        updated = await container.harness.get_step(step.id)

    assert not result.is_error
    assert calls == [("httpx_probe", {"targets": ["example.com"]})]
    assert updated is not None
    assert updated.result_summary.endswith("probes=2")
```

### Step 8 - Add changelog entry

```text
APPEND CHANGELOG.md

- RFC-V14a: planned HARNESS adaptive small-model loop with local fan-out budget and model-tier routing.
```

## Tests

Steps 6 and 7 add focused unit coverage for the new adaptive routing behavior and summary format.

## Post-checks

- [ ] `git diff --stat` only lists `files_will_touch`.
- [ ] `harness_next` still returns one pending step when a pending/running/confirmation step exists.
- [ ] `harness_run` still refuses recursive `harness_*` steps.
- [ ] Public MCP exposure still contains only the existing HARNESS tools in HARNESS-first mode.

## Rollback plan

Run `rollback_cmd` from the front matter.

## Updates to other docs

- `CHANGELOG.md` gets the RFC-V14a planning entry.
- Full user manual updates are deferred to RFC-V14d after the V2 behavior is implemented and benchmarked.

## Notes for executor

- Do not add database columns for this slice; `HarnessStep.recommended_model_tier` already exists.
- Do not call low-level tools from `HarnessPlanner`; it only creates persisted steps.
- Failed steps are not `DONE`, so use `attempted` to avoid retrying the same failed tool.
- `_summarize_result` must stay short because `HarnessStep.result_summary` has a 4096-character limit.
- The test appends use mutable Pydantic entities in test helpers; assigning `failed.status` is already compatible with current entity config.

## Changelog

- 2026-04-24 initial draft by Codex.
