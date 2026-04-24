"""Scan rfcs/RFC-*.md front-matter and regenerate rfcs/INDEX.md status tables.

Usage:
    .venv\\Scripts\\python.exe scripts\\sync_rfc_index.py          # update INDEX.md in place
    .venv\\Scripts\\python.exe scripts\\sync_rfc_index.py --check  # dry-run, exit 1 if drift

Expects each RFC file to have YAML front-matter at the top delimited by
``---`` lines with at minimum:
    id, title, epic, status, blocking_on, owner

See rfcs/RFC-000-TEMPLATE.md for the full schema.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml  # PyYAML is already a project dependency
except ImportError:
    print("ERROR: PyYAML not installed. Run the project's normal install first.", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
RFC_DIR = REPO_ROOT / "rfcs"
INDEX_PATH = RFC_DIR / "INDEX.md"

BEGIN_TABLE_MARKER = "<!-- BEGIN_RFC_TABLE -->"
END_TABLE_MARKER = "<!-- END_RFC_TABLE -->"

EPIC_ORDER = [
    "A-Foundations",
    "B-CoreHardening",
    "C-WebUI-Tier1",
    "D-WebUI-Tier2",
    "E-WebUI-Tier3",
    "F-TUI",
    "G-Tools",
    "H-Release",
    "T-TeamEdition",
    "V-CrossEdition",
]

EPIC_LABEL = {
    "A-Foundations": "Epic A — Engineering foundations",
    "B-CoreHardening": "Epic B — Core hardening",
    "C-WebUI-Tier1": "Epic C — Web UI Tier 1",
    "D-WebUI-Tier2": "Epic D — Web UI Tier 2",
    "E-WebUI-Tier3": "Epic E — Web UI Tier 3",
    "F-TUI": "Epic F — TUI",
    "G-Tools": "Epic G — Tool expansion",
    "H-Release": "Epic H — Release & community",
    "T-TeamEdition": "Epic T — Team Edition",
    "V-CrossEdition": "Epic V — Cross-edition enhancements",
}


@dataclass
class RFCEntry:
    id: str
    title: str
    epic: str
    status: str
    blocking_on: list[str]
    owner: str
    source_file: Path


FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_rfc(path: Path) -> RFCEntry | None:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return None
    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        print(f"WARNING: {path.name} has invalid YAML front-matter: {exc}", file=sys.stderr)
        return None
    if not isinstance(fm, dict):
        return None
    rfc_id = fm.get("id")
    if not rfc_id or rfc_id == "RFC-NNN":  # template placeholder
        return None
    blocking = fm.get("blocking_on") or []
    if isinstance(blocking, str):
        blocking = [blocking]
    return RFCEntry(
        id=str(rfc_id),
        title=str(fm.get("title", "(no title)")).strip(),
        epic=str(fm.get("epic", "unknown")).strip(),
        status=str(fm.get("status", "open")).strip(),
        blocking_on=[str(b).strip() for b in blocking],
        owner=str(fm.get("owner", "")).strip() or "—",
        source_file=path,
    )


def collect_rfcs() -> list[RFCEntry]:
    entries: list[RFCEntry] = []
    for path in sorted(RFC_DIR.glob("RFC-*.md")):
        # Skip the template and stubs file which aren't real RFCs
        if path.name.startswith("RFC-000-") or "STUBS" in path.name.upper():
            continue
        entry = parse_rfc(path)
        if entry is not None:
            entries.append(entry)
    return entries


def render_table(entries: list[RFCEntry]) -> str:
    by_epic: dict[str, list[RFCEntry]] = {}
    for e in entries:
        by_epic.setdefault(e.epic, []).append(e)

    # Order epics per EPIC_ORDER; unknown epics go last
    ordered_epics = [ep for ep in EPIC_ORDER if ep in by_epic]
    ordered_epics += [ep for ep in by_epic if ep not in EPIC_ORDER]

    lines: list[str] = []
    for epic in ordered_epics:
        label = EPIC_LABEL.get(epic, f"Epic {epic}")
        lines.append(f"### {label}")
        lines.append("")
        lines.append("| id      | title | status | blocking_on | owner |")
        lines.append("|---------|-------|--------|-------------|-------|")
        for e in sorted(by_epic[epic], key=lambda x: x.id):
            blocking_cell = ", ".join(e.blocking_on) if e.blocking_on else ""
            title_cell = e.title.replace("|", "\\|")
            lines.append(
                f"| {e.id} | {title_cell} | {e.status} | {blocking_cell} | {e.owner} |"
            )
        lines.append("")
    return "\n".join(lines)


def summary_block(entries: list[RFCEntry]) -> str:
    total = len(entries)
    by_status: dict[str, int] = {}
    for e in entries:
        by_status[e.status] = by_status.get(e.status, 0) + 1
    lines = [
        f"Total RFCs: **{total}**",
        "",
        "| status | count |",
        "|--------|-------|",
    ]
    for s in ("open", "in_progress", "blocked", "done", "abandoned"):
        if by_status.get(s):
            lines.append(f"| {s} | {by_status[s]} |")
    return "\n".join(lines)


def apply_to_index(rendered: str, dry_run: bool) -> bool:
    """Update INDEX.md's marked region. Returns True if it would change content."""
    if not INDEX_PATH.is_file():
        print(f"ERROR: {INDEX_PATH} missing", file=sys.stderr)
        sys.exit(2)
    current = INDEX_PATH.read_text(encoding="utf-8")
    block = f"{BEGIN_TABLE_MARKER}\n{rendered}\n{END_TABLE_MARKER}"

    if BEGIN_TABLE_MARKER in current and END_TABLE_MARKER in current:
        pattern = re.compile(
            re.escape(BEGIN_TABLE_MARKER) + r".*?" + re.escape(END_TABLE_MARKER),
            re.DOTALL,
        )
        updated = pattern.sub(block, current, count=1)
    else:
        # Markers not present yet — add note, don't auto-inject to avoid wrecking layout.
        print(
            f"NOTE: {INDEX_PATH.name} has no sync markers yet. "
            f"Add {BEGIN_TABLE_MARKER} and {END_TABLE_MARKER} around the status tables "
            f"to enable auto-sync. Printing computed tables below.",
            file=sys.stderr,
        )
        print(block)
        return False

    if updated == current:
        return False
    if not dry_run:
        INDEX_PATH.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="dry-run; exit 1 if drift")
    args = ap.parse_args()

    entries = collect_rfcs()
    rendered = render_table(entries) + "\n\n" + summary_block(entries)

    if args.check:
        changed = apply_to_index(rendered, dry_run=True)
        if changed:
            print("DRIFT: INDEX.md out of sync with RFC front-matter. Run without --check.")
            sys.exit(1)
        print(f"OK: INDEX.md in sync ({len(entries)} RFCs).")
        return

    changed = apply_to_index(rendered, dry_run=False)
    if changed:
        print(f"Updated {INDEX_PATH} ({len(entries)} RFCs).")
    else:
        print(f"No changes needed ({len(entries)} RFCs).")


if __name__ == "__main__":
    main()
