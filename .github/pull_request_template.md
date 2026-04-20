## What

<!-- Short description. Link the RFC. -->

Closes: RFC-___

## Checklist

- [ ] `git diff --stat` matches the RFC's intended scope
- [ ] `verify_cmd` passes locally
- [ ] `scripts/full_verify.py` passes locally
- [ ] Unit tests added or updated for new behavior
- [ ] `CHANGELOG.md` `[Unreleased]` updated
- [ ] `THREAT_MODEL.md` / `GAP_ANALYSIS.md` updated if this RFC closes an item
- [ ] No new dependency without `pyproject.toml` bump + `uv lock`

## How to test

```bash
uv sync --frozen --all-extras
uv run pytest tests/ -q
uv run python scripts/full_verify.py
```
