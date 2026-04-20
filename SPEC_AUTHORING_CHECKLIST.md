# Spec Authoring Checklist

> Before committing an RFC, tick every box below. If you can't, **don't open
> the PR** — revise the spec first.
>
> Violation of this checklist is the root cause of the 2026-04-21 RFC audit
> finding that 10 out of 15 RFCs failed pre-flight
> (see [`RFC_AUDIT_PREFLIGHT.md`](./RFC_AUDIT_PREFLIGHT.md)). We are not
> shipping any more RFCs that fail validation.

---

## §0 · Mindset

You are writing for a **weak local model** (think Qwen-7B) that cannot
read your mind. Your job is to reduce the RFC's ambiguity to zero.

**You are not reviewing code. You are writing executable instructions.**

---

## §1 · Read before you write

**Check each file you reference. Open it. Look at it. Copy real strings.**

- [ ] Every path in `files_to_read` exists in the working tree (use
      `ls` / Read tool — don't guess from memory).
- [ ] Every path in `files_will_touch` either exists (for `# modified`) or
      does not exist yet (for `# new`).
- [ ] Every `# new` comment is present on new files — the validator uses this
      to distinguish create-vs-modify.
- [ ] For every `REPLACE` block: you **opened the file and copied** the exact
      SEARCH text. Not reconstructed from memory.
- [ ] SEARCH text is **unique** in the target file (enough surrounding context
      lines to disambiguate).
- [ ] For every imported symbol in your WRITE/REPLACE code: you verified the
      symbol exists in the module you import from.

**Smell test**: if you wrote the RFC without re-opening the target files at
least once, you are probably hallucinating signatures.

---

## §2 · Run the validator before the PR

```powershell
.venv\Scripts\python.exe scripts\validate_rfc.py rfcs\RFC-<id>-*.md
```

- [ ] Exit code is `0` (no errors).
- [ ] Any warnings are acknowledged (add a note or fix).

The validator is automated; no excuse for skipping it.

---

## §3 · Size discipline (hard caps from AGENT_EXECUTION_PROTOCOL §7)

| Cap | Max value |
|-----|-----------|
| `budget.max_files_touched` | 10 |
| `budget.max_new_files` | 6 |
| `budget.max_lines_added` | **400** |
| `budget.max_minutes_human` | 60 |

- [ ] Every cap is declared in `budget:` front-matter.
- [ ] All caps fit under the hard limits above.
- [ ] If your spec exceeds any cap: **split into two RFCs** before submitting.
      A split is not failure; it's good engineering.

---

## §4 · Step grammar

Each `Step N` uses **only** these four indicators. Anything else is prose.

| Indicator | When to use |
|-----------|-------------|
| `WRITE <path>` + fenced code block | Creating a new file whole cloth |
| `REPLACE <path>` + SEARCH/REPLACE markers | Atomic edit of existing file |
| `APPEND <path>` + fenced code block | Add to end of file (e.g. `__init__.py`, CHANGELOG) |
| `RUN <command>` | One shell command, whitelisted prefix only |

- [ ] No step contains prose like "update the file to …" — that's ambiguous.
- [ ] No step uses `&&` / `||` / `;` to chain commands — one RUN per command.
- [ ] Every `RUN` prefix matches the AGENT_EXECUTION_PROTOCOL §6 whitelist
      (`.venv\Scripts\python.exe`, `.venv\Scripts\pytest.exe`, `git status`,
      `git diff`, `git checkout`, `git add`, `git commit`, etc).
- [ ] No step assumes a file created by *another* RFC exists — if it does,
      declare that RFC in `blocking_on`.

---

## §5 · SEARCH block quality

Bad SEARCH blocks are the #1 source of RFC execution failure (see audit
§1.3). Rules for SEARCH text:

- [ ] **Include enough surrounding context** that the block is unique
      (validator C6 enforces this). 3-5 lines usually suffices.
- [ ] **Do not include trailing whitespace** unless it's in the real file.
- [ ] **Match line endings exactly.** If the target file uses CRLF, your
      SEARCH must too (Windows/Git autocrlf: typically LF in working tree).
- [ ] **Quote characters match** (real file uses `"..."` → SEARCH uses `"..."`,
      not `'...'`).
- [ ] **No abbreviations.** If the real line is
      `app = typer.Typer(name="x", help="y", add_completion=False)`, your
      SEARCH must have the whole thing, not `app = typer.Typer(`.

---

## §6 · `verify_cmd` discipline

The `verify_cmd` is the single source of truth for "this RFC worked."

- [ ] `verify_cmd` exits 0 on success, non-zero on failure.
- [ ] It tests the specific behavior this RFC introduces (not "run all tests").
- [ ] It does not require network / external services (or if it does, skip
      cleanly with a warning — like `pytest.skip()`).
- [ ] It is **deterministic** (no race conditions, no `sleep(5)` hope).
- [ ] It runs in < 30 seconds typical, < 120 seconds worst case.
- [ ] If it needs env vars, they are set inline or documented in `Notes for
      executor`.

---

## §7 · `rollback_cmd` discipline

Must leave the working tree at the pre-RFC state.

- [ ] `git checkout -- <each file in files_will_touch that existed before>`
- [ ] `if exist <new file> del <new file>` for every `# new` file.
- [ ] `if exist <new dir> rmdir /s /q <new dir>` for every new directory.
- [ ] Does NOT touch files outside `files_will_touch`.
- [ ] Works on Windows PowerShell (this project's primary dev platform).
- [ ] Mentally test: "if Step 3 fails, can the executor reach baseline by
      running this?"

---

## §8 · Tests requirement

- [ ] Every new public function in WRITE/REPLACE blocks has a corresponding
      test in `tests/unit/`.
- [ ] Every new test file is listed in `files_will_touch` with `# new`.
- [ ] Tests use real code paths where practical; don't mock what you're
      testing.
- [ ] Async tests use `@pytest.mark.asyncio` (or rely on `pytest.ini`'s
      `asyncio_mode = auto`).
- [ ] Test names describe behavior, not implementation:
      `test_fourth_call_refused_when_burst_exceeded` not `test_acquire_false`.

---

## §9 · `blocking_on` completeness

Every RFC your steps reference must be in `blocking_on` — including transitive
deps.

- [ ] If a Step uses a file created by RFC-X, RFC-X is in `blocking_on`.
- [ ] If a Step assumes a signature from RFC-Y, RFC-Y is in `blocking_on`.
- [ ] If you added a dep to `pyproject.toml` that RFC-001 (uv lock) must
      re-lock after, note it in `Notes for executor`.
- [ ] Validator C9 confirms every `blocking_on` RFC file exists — but only
      you can confirm the *transitive* deps are complete.

---

## §10 · Documentation updates

- [ ] `Updates to other docs` section lists every file that changes outside
      `files_will_touch` (CHANGELOG, INDEX, THREAT_MODEL, etc).
- [ ] Each such doc is actually touched by a Step (not just "described").
- [ ] CHANGELOG gets a line under `[Unreleased]` — no exceptions.

---

## §11 · Notes for executor

- [ ] You listed at least 2 gotchas a weak local model would miss:
      - Import path tricks (e.g. `core_errors` at top level, not `core/errors`)
      - Pydantic v2 vs v1 idioms
      - Windows path separators in sqlite URLs
      - Typer callback ordering
      - SQLAlchemy async lazy-load traps
- [ ] If the RFC depends on an env var or config, it's listed here.
- [ ] If there's a known non-obvious failure mode, it's mentioned here.

---

## §12 · Final self-test

Before merging:

- [ ] Mentally walk through every Step in order, pretending you know nothing
      about the project except what the RFC tells you.
- [ ] Every step is deterministic — same input, same output.
- [ ] The Post-checks list has at least 3 human-verifiable items.
- [ ] You ran `scripts/validate_rfc.py <file>` and it passed.
- [ ] You opened the RFC file with `audit/rfc/` Cursor skill and it
      returned READY.

---

## Appendix · The 5 defect classes (names to remember)

From RFC_AUDIT_PREFLIGHT.md §1:

| # | Name | Example | Guard |
|---|------|---------|-------|
| 1 | Config hallucination | `default-groups` in wrong spec | §1 (read the tool docs) |
| 2 | Phantom file reference | `cli/__main__.py` doesn't exist | §1 (open the tree) |
| 3 | SEARCH block hallucination | `def check_target` doesn't exist | §5 (copy, don't compose) |
| 4 | Missing from `files_will_touch` | Step writes un-listed path | §4 (validate explicitly) |
| 5 | Budget cap overrun | >400 lines in one RFC | §3 (split, don't inflate) |

---

## Changelog

- **2026-04-21 v1.0** — Initial. Reaction to 10/15 RFCs failing audit on
  first execution attempt.
