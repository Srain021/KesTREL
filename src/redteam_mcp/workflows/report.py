"""Pentest report generator.

Assembles a Markdown report from the structured audit log produced by
previous tool calls. Zero-IO for the network — the "data" is whatever the
LLM already has in its context window plus any JSON it asks to include.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jinja2 import Template

from ..logging import audit_event, get_logger
from ..tools.base import ToolResult, ToolSpec


_TEMPLATE = Template(
    """\
# {{ title }}

**Engagement date:** {{ date }}
**Authorized scope:** `{{ scope }}`
**Tester:** {{ tester or "N/A" }}

---

## Executive summary

{{ exec_summary or "_Summary to be written by the operator._" }}

---

## Methodology

{{ methodology }}

---

## Findings

{% if findings %}
{% for f in findings %}
### {{ loop.index }}. [{{ f.severity|upper }}] {{ f.title }}

- **Target:** `{{ f.target }}`
- **Detected by:** {{ f.tool or "N/A" }}
- **CWE / CVE:** {{ f.cwe or "N/A" }} / {{ f.cve or "N/A" }}

**Description.**
{{ f.description or "" }}

**Evidence.**
```
{{ f.evidence or "" }}
```

**Remediation.**
{{ f.remediation or "_Not specified._" }}

---
{% endfor %}
{% else %}
_No findings recorded._
{% endif %}

## Appendix: tool invocations

{% if invocations %}
| Time | Tool | Args |
|------|------|------|
{% for i in invocations -%}
| {{ i.ts }} | `{{ i.tool }}` | {{ i.args }} |
{% endfor %}
{% else %}
_No invocations recorded._
{% endif %}
"""
)


class ReportWorkflow:
    def __init__(self) -> None:
        self.log = get_logger("workflow.report")

    def spec(self) -> ToolSpec:
        async def handler(arguments: dict[str, Any]) -> ToolResult:
            title = arguments.get("title", "Penetration Test Report")
            scope = arguments.get("scope", "")
            tester = arguments.get("tester", "")
            exec_summary = arguments.get("executive_summary", "")
            methodology = arguments.get(
                "methodology",
                "Reconnaissance, vulnerability scanning, manual validation, and reporting.",
            )
            findings = arguments.get("findings", []) or []
            invocations = arguments.get("invocations", []) or []

            rendered = _TEMPLATE.render(
                title=title,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                scope=scope,
                tester=tester,
                exec_summary=exec_summary,
                methodology=methodology,
                findings=findings,
                invocations=invocations,
            )
            audit_event(
                self.log,
                "report.generate",
                findings=len(findings),
                invocations=len(invocations),
            )
            return ToolResult(
                text=rendered,
                structured={
                    "title": title,
                    "scope": scope,
                    "findings_count": len(findings),
                    "markdown": rendered,
                },
            )

        return ToolSpec(
            name="generate_pentest_report",
            description=(
                "Render a professional Markdown pentest report from structured "
                "finding + invocation data. The LLM supplies the data; this tool "
                "produces the human-readable document."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "scope": {"type": "string"},
                    "tester": {"type": "string"},
                    "executive_summary": {"type": "string"},
                    "methodology": {"type": "string"},
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["title", "severity", "target"],
                            "properties": {
                                "title": {"type": "string"},
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "high", "medium", "low", "info"],
                                },
                                "target": {"type": "string"},
                                "tool": {"type": "string"},
                                "cwe": {"type": "string"},
                                "cve": {"type": "string"},
                                "description": {"type": "string"},
                                "evidence": {"type": "string"},
                                "remediation": {"type": "string"},
                            },
                        },
                    },
                    "invocations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ts": {"type": "string"},
                                "tool": {"type": "string"},
                                "args": {"type": "string"},
                            },
                        },
                    },
                },
                "additionalProperties": False,
            },
            handler=handler,
            tags=["workflow", "report"],
        )
