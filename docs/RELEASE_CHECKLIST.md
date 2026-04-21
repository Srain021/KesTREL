# v1.0 Release Checklist

This checklist is the human gate for publishing `kestrel-mcp` v1.0.0.

## Required Green Checks

- `scripts/full_verify.py` reports 8/8.
- `ruff check src/ tests/` is clean.
- `mypy --strict src/kestrel_mcp/core src/kestrel_mcp/domain src/kestrel_mcp/webui` is clean.
- `python -m kestrel_mcp version` prints `1.0.0`.
- `scripts/validate_rfc.py rfcs/RFC-*.md --summary` has no unexpected open-RFC failures.

## Release Metadata

- `pyproject.toml` version is `1.0.0`.
- `uv.lock` local package entry is `1.0.0`.
- `src/kestrel_mcp/__init__.py` `__version__` is `1.0.0`.
- `config/default.yaml` server version is `1.0.0`.
- `CHANGELOG.md` has `[1.0.0] - 2026-04-21`.

## Tag And Publish

After the RFC-H04 commit is reviewed and accepted, create the release tag:

```powershell
git tag -a v1.0.0 -m "kestrel-mcp v1.0.0"
git push origin v1.0.0
```

The tag push triggers the release workflow from RFC-H02. Do not create the tag
inside the RFC commit itself.

## Post-release Smoke

- Confirm the GitHub Release was created.
- Confirm the PyPI package install works in a fresh environment.
- Confirm the GHCR image starts and responds to `kestrel version`.
