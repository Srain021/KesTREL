"""Pre-flight validator for RFC files.

Detects spec-author mistakes BEFORE an agent starts execution. Stops 80%+ of
"RFC failed at Step N" incidents by catching them at write time instead of
execute time.

Checks:
    C1  Front-matter has all required fields and valid values.
    C2  Every `files_to_read` path exists in the working tree.
    C3  Every `files_will_touch` file marked `# modified` exists.
    C4  Every `files_will_touch` file marked `# new` does NOT exist
        (would collide on WRITE).
    C5  Every `RUN <cmd>` prefix matches the whitelist from
        AGENT_EXECUTION_PROTOCOL §6.
    C6  Every `REPLACE <path>` block has a SEARCH/REPLACE pair with the
        correct markers, and the SEARCH text matches exactly ONE
        occurrence in the target file.
    C7  Every `WRITE <path>` targets a path inside `files_will_touch`.
    C8  Every `APPEND <path>` targets a path inside `files_will_touch`.
    C9  `blocking_on` entries reference RFC files that exist.
    C10 Budget fields are present and reasonable.

Usage:
    python scripts/validate_rfc.py rfcs/RFC-007-*.md
    python scripts/validate_rfc.py rfcs/RFC-*.md
    python scripts/validate_rfc.py rfcs/RFC-*.md --json
    python scripts/validate_rfc.py rfcs/RFC-*.md --summary

Exit codes:
    0 — all checked RFCs pass
    1 — at least one RFC has at least one error
    2 — tool itself failed (e.g. missing PyYAML)
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent

# RUN command prefix whitelist from AGENT_EXECUTION_PROTOCOL §6.
# Any RUN line must start with one of these (after stripping leading whitespace).
RUN_WHITELIST = (
    ".venv\\Scripts\\python.exe",
    ".venv\\Scripts\\pytest.exe",
    ".venv\\Scripts\\ruff.exe",
    ".venv\\Scripts\\mypy.exe",
    ".venv\\Scripts\\alembic.exe",
    ".venv/bin/python",
    ".venv/bin/pytest",
    ".venv/bin/ruff",
    ".venv/bin/mypy",
    ".venv/bin/alembic",
    "git status",
    "git diff",
    "git log",
    "git checkout",
    "git rev-parse",
    "git branch",
    "git add",
    "git commit",
)

REQUIRED_FM_FIELDS = (
    "id", "title", "epic", "status", "owner", "role",
    "blocking_on", "budget", "files_to_read", "files_will_touch",
    "verify_cmd", "rollback_cmd",
)

BUDGET_FIELDS = (
    "max_files_touched", "max_new_files", "max_lines_added",
    "max_minutes_human", "max_tokens_model",
)

VALID_STATUSES = {"open", "in_progress", "blocked", "done", "abandoned"}

# Hard caps consistent with AGENT_EXECUTION_PROTOCOL §7.
BUDGET_HARD_CAPS = {
    "max_files_touched": 10,
    "max_new_files": 6,
    "max_lines_added": 400,
    "max_minutes_human": 60,
}


@dataclass
class Issue:
    level: str      # "error" | "warning"
    check: str      # C1..C10
    step: int | None  # step number or None for front-matter issues
    message: str


@dataclass
class RFCReport:
    path: Path
    rfc_id: str
    issues: list[Issue] = field(default_factory=list)
    steps_seen: int = 0

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------- parsers ----------

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Matches instruction lines: WRITE, REPLACE, APPEND, RUN — flexible whitespace.
INSTRUCTION_RE = re.compile(
    r"^\s*(WRITE|REPLACE|APPEND|RUN)\s+(.+?)\s*$", re.MULTILINE
)
STEP_RE = re.compile(r"^###\s+Step\s+(\d+)\b", re.MULTILINE)

SEARCH_MARKER = "<<<<<<< SEARCH"
SEPARATOR = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"


def parse_front_matter(text: str) -> dict | None:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return fm if isinstance(fm, dict) else None


_FWT_LINE_RE = re.compile(r"^\s{2,}-\s*(\S+?)(?:\s+#\s*(.*?))?\s*$")


def extract_files_will_touch_paths_from_fm_text(fm_text: str) -> tuple[set[str], set[str]]:
    """Walk the raw YAML front-matter text to recover ``# new`` / ``# modified``
    line comments that ``yaml.safe_load`` strips. Returns (all_paths, new_paths).
    """
    all_paths: set[str] = set()
    new_paths: set[str] = set()
    in_block = False
    for line in fm_text.splitlines():
        if re.match(r"^\s*files_will_touch\s*:\s*$", line):
            in_block = True
            continue
        if in_block:
            # End of block: a new top-level key (starts with non-space letter).
            if re.match(r"^\S", line):
                break
            m = _FWT_LINE_RE.match(line)
            if not m:
                continue
            path = m.group(1).strip().strip("\"'")
            comment = (m.group(2) or "").lower()
            norm = _norm_path(path)
            all_paths.add(norm)
            if "new" in comment:
                new_paths.add(norm)
    return all_paths, new_paths


def extract_files_will_touch_paths(fm: dict) -> tuple[set[str], set[str]]:
    """Kept for compatibility; prefer the _from_fm_text variant which preserves
    the inline ``# new`` comments."""
    all_paths: set[str] = set()
    for entry in (fm.get("files_will_touch") or []):
        if isinstance(entry, str) and entry.strip():
            all_paths.add(_norm_path(entry.strip()))
    return all_paths, set()  # can't recover new/modified from yaml dict


def _norm_path(p: str) -> str:
    return p.replace("\\", "/").strip()


def extract_replace_blocks(rfc_body: str) -> list[tuple[int, str, str, str]]:
    """Return list of (step_num_or_neg1, target_path, search_text, replace_text).

    step_num_or_neg1 is the nearest ### Step N heading above the REPLACE.
    """
    # Build (offset, step_num) lookup.
    step_offsets = [(m.start(), int(m.group(1))) for m in STEP_RE.finditer(rfc_body)]

    def step_for(offset: int) -> int:
        step = -1
        for off, num in step_offsets:
            if off <= offset:
                step = num
            else:
                break
        return step

    blocks: list[tuple[int, str, str, str]] = []
    # Pattern: REPLACE <path> ... then within the next code block, SEARCH/=====/REPLACE markers.
    for m in re.finditer(r"^REPLACE\s+(.+?)\s*$", rfc_body, re.MULTILINE):
        path = m.group(1).strip()
        # search the following region for a SEARCH marker up to end-of-fence or next instruction
        start = m.end()
        # Window: up to 3000 chars or next REPLACE/WRITE/APPEND/RUN or closing fence
        end = len(rfc_body)
        for next_m in re.finditer(
            r"^(REPLACE|WRITE|APPEND|RUN)\s+", rfc_body[start + 1:], re.MULTILINE
        ):
            end = start + 1 + next_m.start()
            break
        window = rfc_body[start:end]

        search_idx = window.find(SEARCH_MARKER)
        sep_idx = window.find(SEPARATOR, search_idx + 1) if search_idx >= 0 else -1
        repl_idx = window.find(REPLACE_MARKER, sep_idx + 1) if sep_idx >= 0 else -1

        if search_idx < 0 or sep_idx < 0 or repl_idx < 0:
            blocks.append((step_for(m.start()), path, "", ""))
            continue

        search_text = window[search_idx + len(SEARCH_MARKER):sep_idx].strip("\n")
        replace_text = window[sep_idx + len(SEPARATOR):repl_idx].strip("\n")
        blocks.append((step_for(m.start()), path, search_text, replace_text))

    return blocks


def extract_instructions(rfc_body: str) -> list[tuple[int, str, str]]:
    """Return list of (step_num, kind, argument). Skips REPLACE fence markers
    that accidentally look like instructions (they don't)."""
    step_offsets = [(m.start(), int(m.group(1))) for m in STEP_RE.finditer(rfc_body)]

    def step_for(offset: int) -> int:
        step = -1
        for off, num in step_offsets:
            if off <= offset:
                step = num
            else:
                break
        return step

    out: list[tuple[int, str, str]] = []
    for m in INSTRUCTION_RE.finditer(rfc_body):
        kind = m.group(1)
        arg = m.group(2).strip()
        # Skip SEARCH/=====/REPLACE fence lines that contain the keyword REPLACE
        # — SEARCH/REPLACE markers have distinctive <<<<<<<  / >>>>>>>>
        preceding_20 = rfc_body[max(0, m.start() - 20): m.start()]
        if "<<<<<<<" in preceding_20 or ">>>>>>>" in preceding_20:
            continue
        out.append((step_for(m.start()), kind, arg))
    return out


# ---------- validators (C1..C10) ----------

def check_front_matter(fm: dict | None, rep: RFCReport) -> bool:
    if fm is None:
        rep.issues.append(Issue("error", "C1", None, "missing or invalid YAML front-matter"))
        return False
    for f in REQUIRED_FM_FIELDS:
        if f not in fm:
            rep.issues.append(
                Issue("error", "C1", None, f"front-matter missing required field '{f}'")
            )
    status = fm.get("status", "")
    if status not in VALID_STATUSES:
        rep.issues.append(
            Issue("error", "C1", None, f"status '{status}' not one of {sorted(VALID_STATUSES)}")
        )
    bud = fm.get("budget", {})
    if isinstance(bud, dict):
        for bf in BUDGET_FIELDS:
            if bf not in bud:
                rep.issues.append(Issue("warning", "C10", None, f"budget missing '{bf}'"))
        for bf, cap in BUDGET_HARD_CAPS.items():
            val = bud.get(bf)
            if isinstance(val, (int, float)) and val > cap:
                rep.issues.append(
                    Issue("error", "C10", None,
                          f"budget.{bf}={val} exceeds hard cap {cap} — split RFC")
                )
    else:
        rep.issues.append(Issue("error", "C10", None, "budget is not a mapping"))
    return True


def check_files_to_read(fm: dict, rep: RFCReport, write_targets: set[str]) -> None:
    for entry in (fm.get("files_to_read") or []):
        if not isinstance(entry, str):
            continue
        p = _norm_path(entry.partition("#")[0])
        if not p:
            continue
        abs_p = REPO_ROOT / p
        if not abs_p.exists():
            # Give a pass if this path will be *created* by this same RFC.
            if p in write_targets:
                continue
            rep.issues.append(
                Issue("error", "C2", None, f"files_to_read entry '{p}' does not exist")
            )


def check_files_will_touch(
    fm: dict, rep: RFCReport, new_paths: set[str], all_paths: set[str]
) -> None:
    for p in all_paths:
        abs_p = REPO_ROOT / p
        if p in new_paths:
            if abs_p.exists():
                rep.issues.append(
                    Issue("error", "C4", None,
                          f"files_will_touch '{p}' is marked 'new' but already exists")
                )
        else:
            if not abs_p.exists():
                rep.issues.append(
                    Issue("warning", "C3", None,
                          f"files_will_touch '{p}' is not marked 'new' but missing — "
                          f"RFC may assume earlier RFC created it")
                )


def check_instructions(
    instructions: list[tuple[int, str, str]],
    write_targets: set[str],
    rep: RFCReport,
) -> None:
    for step, kind, arg in instructions:
        rep.steps_seen = max(rep.steps_seen, step)
        if kind == "RUN":
            ok = any(arg.startswith(prefix) for prefix in RUN_WHITELIST)
            if not ok:
                rep.issues.append(
                    Issue("error", "C5", step,
                          f"RUN '{arg[:80]}' not in AGENT_EXECUTION_PROTOCOL §6 whitelist")
                )
            # Detect shell chaining, but NOT ';' inside a -c "..." Python string.
            in_python_c = bool(re.search(r'-c\s+["\'].*;', arg))
            if (" && " in arg or " || " in arg) or (" ; " in arg and not in_python_c):
                rep.issues.append(
                    Issue("warning", "C5", step,
                          f"RUN chains commands ('{arg[:50]}'); protocol requires one action per RUN")
                )
        elif kind == "WRITE":
            target = _norm_path(arg)
            if target not in write_targets:
                rep.issues.append(
                    Issue("error", "C7", step,
                          f"WRITE '{target}' is not listed in files_will_touch")
                )
        elif kind == "APPEND":
            target = _norm_path(arg)
            if target not in write_targets:
                rep.issues.append(
                    Issue("error", "C8", step,
                          f"APPEND '{target}' is not listed in files_will_touch")
                )


def check_replace_blocks(
    blocks: list[tuple[int, str, str, str]],
    write_targets: set[str],
    rep: RFCReport,
) -> None:
    for step, path, search, _replace in blocks:
        target = _norm_path(path)
        abs_p = REPO_ROOT / target
        if target not in write_targets:
            rep.issues.append(
                Issue("error", "C7", step, f"REPLACE '{target}' not in files_will_touch")
            )
        if not search:
            rep.issues.append(
                Issue("error", "C6", step,
                      f"REPLACE '{target}' has no SEARCH block (marker missing or empty)")
            )
            continue
        if not abs_p.exists():
            rep.issues.append(
                Issue("error", "C6", step,
                      f"REPLACE target '{target}' does not exist; cannot verify SEARCH")
            )
            continue
        try:
            content = abs_p.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            rep.issues.append(
                Issue("error", "C6", step, f"cannot read '{target}': {exc}")
            )
            continue
        count = content.count(search)
        if count == 0:
            # Offer a hint: is there a similar-looking line?
            hint = _find_near_match(content, search)
            rep.issues.append(
                Issue("error", "C6", step,
                      f"REPLACE '{target}' SEARCH block matches 0 times. "
                      f"First 60 chars of SEARCH: {search[:60]!r}. "
                      + (f"Near miss found: {hint!r}" if hint else "No near-miss found."))
            )
        elif count > 1:
            rep.issues.append(
                Issue("error", "C6", step,
                      f"REPLACE '{target}' SEARCH block matches {count} times — "
                      f"must be unique. Add more context lines.")
            )


def _find_near_match(content: str, needle: str) -> str | None:
    """Return a line from `content` that shares >= 3 significant tokens with
    the first line of `needle`. Quick-and-dirty; for human hint only."""
    first_line = needle.strip().splitlines()[0] if needle.strip() else ""
    tokens = set(re.findall(r"\w{3,}", first_line))
    if len(tokens) < 2:
        return None
    best_score = 0
    best = None
    for line in content.splitlines():
        line_tokens = set(re.findall(r"\w{3,}", line))
        common = tokens & line_tokens
        if len(common) >= 3 and len(common) > best_score:
            best_score = len(common)
            best = line.strip()
    return best


def check_blocking_on(fm: dict, rep: RFCReport) -> None:
    rfcs_dir = REPO_ROOT / "rfcs"
    for dep in (fm.get("blocking_on") or []):
        if not isinstance(dep, str):
            continue
        # Look for rfcs/RFC-<dep>-*.md
        matches = list(rfcs_dir.glob(f"{dep}-*.md"))
        if not matches:
            rep.issues.append(
                Issue("error", "C9", None,
                      f"blocking_on '{dep}' — no matching RFC file found in rfcs/")
            )


# ---------- driver ----------

def validate_rfc(path: Path) -> RFCReport:
    text = path.read_text(encoding="utf-8")
    fm = parse_front_matter(text)
    rfc_id = (fm.get("id") if fm else None) or path.stem
    rep = RFCReport(path=path, rfc_id=rfc_id)

    if not check_front_matter(fm, rep):
        return rep
    assert fm is not None

    # Recover the inline `# new` / `# modified` comments from the raw YAML text
    # — yaml.safe_load drops them.
    fm_match = FRONT_MATTER_RE.match(text)
    fm_text = fm_match.group(1) if fm_match else ""
    all_paths, new_paths = extract_files_will_touch_paths_from_fm_text(fm_text)
    check_files_to_read(fm, rep, all_paths)
    check_files_will_touch(fm, rep, new_paths, all_paths)
    check_blocking_on(fm, rep)

    # Parse the body below front-matter.
    body_start = FRONT_MATTER_RE.match(text)
    body = text[body_start.end():] if body_start else text

    instructions = extract_instructions(body)
    check_instructions(instructions, all_paths, rep)

    replace_blocks = extract_replace_blocks(body)
    check_replace_blocks(replace_blocks, all_paths, rep)

    return rep


def format_report_human(reports: list[RFCReport], summary_only: bool) -> str:
    lines: list[str] = []
    total = len(reports)
    passing = sum(1 for r in reports if r.ok)
    total_errors = sum(len(r.errors) for r in reports)
    total_warnings = sum(len(r.warnings) for r in reports)
    lines.append("=" * 74)
    lines.append(
        f"RFC Pre-flight Validation — {total} file(s), "
        f"{passing} pass, {total - passing} fail "
        f"({total_errors} errors, {total_warnings} warnings)"
    )
    lines.append("=" * 74)
    for rep in reports:
        badge = "PASS" if rep.ok else "FAIL"
        lines.append("")
        lines.append(f"[{badge}] {rep.rfc_id}  ({rep.path.name})")
        if summary_only and rep.ok:
            continue
        if not rep.issues:
            lines.append("  (no issues)")
            continue
        for iss in rep.issues:
            loc = f"Step {iss.step}" if iss.step and iss.step > 0 else "front-matter"
            sigil = "ERR" if iss.level == "error" else "warn"
            lines.append(f"  [{sigil}] {iss.check} @ {loc}: {iss.message}")
    lines.append("")
    lines.append("=" * 74)
    return "\n".join(lines)


def format_report_json(reports: list[RFCReport]) -> str:
    out = []
    for rep in reports:
        out.append({
            "rfc_id": rep.rfc_id,
            "path": str(rep.path.relative_to(REPO_ROOT)),
            "ok": rep.ok,
            "issues": [
                {"level": i.level, "check": i.check, "step": i.step, "message": i.message}
                for i in rep.issues
            ],
        })
    return json.dumps(out, indent=2, ensure_ascii=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("patterns", nargs="+", help="RFC file paths or globs")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--summary", action="store_true", help="only show failing RFCs")
    args = ap.parse_args()

    paths: list[Path] = []
    for pat in args.patterns:
        pat_path = Path(pat)
        if pat_path.is_file():
            paths.append(pat_path.resolve())
            continue
        for match in glob.glob(pat, recursive=True):
            p = Path(match)
            if p.is_file() and p.suffix == ".md":
                paths.append(p.resolve())

    if not paths:
        print("ERROR: no RFC files matched", file=sys.stderr)
        sys.exit(2)

    # Deduplicate, skip templates and stubs.
    seen = set()
    clean = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        if p.name.startswith("RFC-000") or "STUBS" in p.name.upper():
            continue
        clean.append(p)

    reports = [validate_rfc(p) for p in sorted(clean)]

    if args.json:
        print(format_report_json(reports))
    else:
        print(format_report_human(reports, summary_only=args.summary))

    if any(not r.ok for r in reports):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
