"""Bootstrap a crew-ready Team edition install.

Called by `kestrel team bootstrap --name <slug>`. See RFC-T08.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from redteam_mcp.config import Settings
from redteam_mcp.core.services import ServiceContainer
from redteam_mcp.domain import entities as ent


@dataclass
class BootstrapReport:
    name: str
    edition: str
    data_dir: Path
    engagement_id: str | None = None
    scope_added: list[str] = field(default_factory=list)
    doctor_warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def render(self) -> str:
        lines = [
            "=" * 62,
            "  Kestrel Team Edition - Bootstrap Report",
            "=" * 62,
            f"  Engagement:    {self.name}  ({'dry-run' if self.dry_run else 'created'})",
            f"  Edition:       {self.edition}",
            f"  Data dir:      {self.data_dir}",
            f"  Engagement id: {self.engagement_id or '(would be created)'}",
            f"  Scope entries: {len(self.scope_added)}",
        ]
        for s in self.scope_added:
            lines.append(f"    - {s}")
        if self.doctor_warnings:
            lines.append("  Doctor warnings:")
            for w in self.doctor_warnings:
                lines.append(f"    ! {w}")
        lines += [
            "",
            "  Next steps:",
            f"    1. Start server:  kestrel --edition team serve",
            f"    2. Point your LLM client at the stdio transport",
            f"    3. Active engagement via env:  "
            f"$env:KESTREL_ENGAGEMENT = '{self.name}'",
            "",
            "=" * 62,
        ]
        return "\n".join(lines)


def _doctor_warnings() -> list[str]:
    warnings: list[str] = []
    for tool in ("nuclei", "sliver-server", "caido"):
        if shutil.which(tool) is None:
            warnings.append(f"{tool} not on PATH (feature degraded)")
    if not os.getenv("SHODAN_API_KEY"):
        warnings.append("SHODAN_API_KEY unset (OSINT search disabled)")
    return warnings


async def _do_bootstrap(
    settings: Settings,
    name: str,
    scope_entries: Iterable[str],
    dry_run: bool,
) -> BootstrapReport:
    # Resolve data_dir the same way ServiceContainer.default_on_disk does.
    data_dir = Path(os.environ.get("KESTREL_DATA_DIR", "~/.kestrel")).expanduser()

    report = BootstrapReport(
        name=name,
        edition=settings.edition,
        data_dir=data_dir,
        dry_run=dry_run,
        doctor_warnings=_doctor_warnings(),
        scope_added=list(scope_entries) if dry_run else [],
    )

    if dry_run:
        return report

    data_dir.mkdir(parents=True, exist_ok=True)

    container = ServiceContainer.default_on_disk(data_dir=data_dir)
    await container.initialise()
    try:
        engagement = await container.engagement.create(
            name=name,
            display_name=name.replace("-", " ").replace("_", " ").title(),
            engagement_type=ent.EngagementType.RED_TEAM,
            client="internal-crew",
            owners=[],
        )
        report.engagement_id = str(engagement.id)

        for entry in scope_entries:
            entry = entry.strip()
            if not entry:
                continue
            await container.scope.add_entry(engagement_id=engagement.id, pattern=entry)
            report.scope_added.append(entry)
    finally:
        await container.dispose()

    return report


def bootstrap(
    name: str,
    scope: str | None = None,
    dry_run: bool = False,
    edition: str | None = "team",
) -> BootstrapReport:
    """Top-level entry point. Builds Settings, runs the async core, returns
    the report dataclass.
    """

    settings = Settings.build(edition=edition)
    entries = [s.strip() for s in (scope or "").split(",") if s.strip()]
    return asyncio.run(_do_bootstrap(settings, name, entries, dry_run))
