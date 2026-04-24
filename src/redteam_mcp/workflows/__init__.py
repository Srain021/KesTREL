"""High-level cross-tool workflows.

A workflow is a :class:`ToolSpec` whose handler internally calls multiple
other tools' handlers (not through the MCP wire — directly in-process)
and returns a single aggregated :class:`ToolResult`. The LLM sees a
workflow as a single tool, which dramatically reduces round-trip cost
when chaining scans.

Phase 1 workflows:
    * ``recon_target``               — Shodan + optional Nuclei baseline
    * ``generate_pentest_report``    — Markdown/JSON report from collected
                                      findings and invocation traces

Future:
    * ``full_vuln_scan``             — nmap-style discovery → Nuclei by service
    * ``exploit_chain``              — finding → Sliver payload generation
"""

from __future__ import annotations

from ..config import Settings
from ..security import ScopeGuard
from ..tools import load_modules
from ..tools.base import ToolSpec
from .recon import ReconWorkflow
from .report import ReportWorkflow


def load_workflow_specs(settings: Settings, scope_guard: ScopeGuard) -> list[ToolSpec]:
    """Build workflow ToolSpec objects by wiring them to enabled tool modules."""

    specs: list[ToolSpec] = []

    modules = load_modules(settings, scope_guard)
    handlers = {spec.name: spec.handler for m in modules for spec in m.specs()}

    if {"shodan_search", "shodan_host"}.issubset(handlers):
        recon = ReconWorkflow(settings, scope_guard)
        specs.append(
            recon.spec(
                shodan_search=handlers["shodan_search"],
                shodan_host=handlers["shodan_host"],
                nuclei_scan=handlers.get("nuclei_scan"),
            )
        )

    specs.append(ReportWorkflow().spec())

    return specs


__all__ = ["load_workflow_specs"]
