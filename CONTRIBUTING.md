# Contributing to Kestrel-MCP

Thanks for your interest. This project follows a **strict RFC-driven workflow**
that keeps weak local models (Qwen-7B, Llama-3-8B) capable of executing changes
safely. Read this before your first PR.

---

## TL;DR

1. **Don't open a PR without an RFC.** Every change (even typo fixes — no,
   especially typo fixes) is specified in `rfcs/RFC-<id>-<slug>.md` first.
2. **Run `scripts\full_verify.py`** before and after. Must be `8/8 checks passed`.
3. **One RFC = one commit = one PR.** No bundling.
4. **Commit message format**: `RFC-<id>: <title>`.

---

## Workflow

### 1. Pick or author an RFC

- Browse open RFCs in [`rfcs/INDEX.md`](./rfcs/INDEX.md).
- Pick one whose `blocking_on` are all `done` — these are "unblocked".
- If no RFC covers your idea, **author one first**: see
  [`rfcs/RFC-000-TEMPLATE.md`](./rfcs/RFC-000-TEMPLATE.md) and follow the
  `plan/` Cursor skill (or do the steps manually).

### 2. Execute the RFC

Every RFC has explicit `files_to_read`, `files_will_touch`, `Steps`,
`verify_cmd`, `rollback_cmd`. Follow them **exactly**:

- Read only `files_to_read`. No `grep` / `find` / recursive browse.
- Modify only `files_will_touch`.
- Use only `WRITE` / `REPLACE` / `APPEND` / `RUN` indicators.
- If any step fails: up to 3 retries with clean `git checkout -- .` between
  each. After 3 → set RFC `status: blocked`, stop, ask a reviewer.

See [`AGENT_EXECUTION_PROTOCOL.md`](./AGENT_EXECUTION_PROTOCOL.md) for the full
contract.

### 3. Verify

```powershell
.\.venv\Scripts\python.exe scripts\full_verify.py
# Must show: Result: 8/8 checks passed.
```

Plus the RFC's `verify_cmd`. Both must be green.

### 4. Update the status table

```powershell
.\.venv\Scripts\python.exe scripts\sync_rfc_index.py
```

This refreshes `rfcs/INDEX.md` from RFC front-matter. Commit the result.

### 5. Update CHANGELOG.md

Add a line under `[Unreleased]` referencing your RFC:

```markdown
### Added
- `RFC-007` — FastAPI app skeleton (<brief summary>).
```

### 6. Commit

```bash
git add <files_will_touch> CHANGELOG.md rfcs/INDEX.md rfcs/RFC-<id>-*.md
git commit -m "RFC-<id>: <title>"
```

No squash, no amend (unless the RFC itself says to).

### 7. Open PR

Use the following PR template (paste into PR description):

```markdown
## RFC
- RFC-<id>: <title>
- Status transition: open → done

## Scope
- Files changed: <N> (matches RFC's files_will_touch)
- Lines added: <N> (within RFC budget of <M>)

## Verification
- [x] `scripts\full_verify.py` 8/8 green
- [x] RFC's `verify_cmd` green
- [x] `rfcs/INDEX.md` updated via sync script
- [x] `CHANGELOG.md` entry added

## Notes
<any surprises, deviations, or follow-up work>
```

---

## Style

### Python

- Python 3.12, with `from __future__ import annotations` at the top of every file
- Pydantic v2 idioms (`model_dump`, not v1 `.dict()`)
- SQLAlchemy 2.0 async (explicit `select()`, not legacy `query()`)
- Google-style docstrings on public functions
- Type hints on every public signature; `mypy --strict` clean
- `ruff` clean (config in `pyproject.toml`)

### Error handling

Use specific classes from `src/kestrel_mcp/core_errors.py`:

```python
from kestrel_mcp.core_errors import AuthorizationError

if not allowed:
    raise AuthorizationError("target out of scope", target=target_str)
```

Never `except Exception:` without re-raise.

### Subprocess

Always argv list, never `shell=True`:

```python
# good
await asyncio.create_subprocess_exec("nuclei", "-u", target, ...)

# bad — never do this
subprocess.run(f"nuclei -u {target}", shell=True)
```

### Paths

User-supplied paths must go through `core.paths.safe_path()`:

```python
from kestrel_mcp.core.paths import safe_path

resolved = safe_path(base=artifact_dir, user_input=filename)
```

### Logging

Use `structlog`, never `print`:

```python
import structlog
log = structlog.get_logger(__name__)
log.info("event_name", field=value)
```

Sensitive strings pass through `core.redact.redact()` first.

---

## Testing

- **Unit tests** mirror source structure: `tests/unit/<module>/test_<thing>.py`
- **Async tests** need `@pytest.mark.asyncio` (mode=auto in pyproject.toml)
- **One behavior per test**; name tests after the behavior
- **No trivial tests** (`assert True`, tautologies). If the behavior is
  trivial, skip the test.
- **No mocking the thing you're testing** (integration tests run real code
  paths when possible).

---

## What NOT to do

- ❌ Don't install dependencies with `pip install <x>` directly. Edit
  `pyproject.toml` and wait for RFC-001's `uv lock` step.
- ❌ Don't push to `main` directly. PRs only.
- ❌ Don't `git commit --amend` a pushed commit.
- ❌ Don't bundle multiple RFCs in one PR — each gets its own.
- ❌ Don't modify `verify_cmd` to make it pass. That's cheating.
- ❌ Don't skip the CHANGELOG entry. Reviewers will send it back.

---

## Getting help

- **Stuck mid-RFC**: run the `audit/rfc/` Cursor skill to validate the RFC
  itself. If the RFC has a bug, report via `plan/split-rfc/` instead of
  forcing the execution.
- **Environment broken**: `scripts\full_verify.py` output tells you which of
  8 checks failed; fix that first.
- **Found a new gap**: open an issue or draft a new RFC (see `plan/` skill).

---

## Code of conduct

Be specific. Be evidence-based. Be kind about correctness, firm about protocol.

Thanks for contributing.
