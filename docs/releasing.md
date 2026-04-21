# Releasing

Kestrel releases are tag-driven.

1. Confirm `scripts/full_verify.py`, ruff, mypy, and the RFC validator are green.
2. Finalize the changelog entry for the version.
3. Create an annotated tag, for example:

```powershell
git tag -a v1.0.0 -m "kestrel-mcp v1.0.0"
git push origin v1.0.0
```

The release workflow then builds Python distributions, publishes to PyPI using
trusted publishing, builds a Docker image, pushes it to GHCR, and creates a
GitHub Release.

## Required Repository Setup

- PyPI trusted publisher is configured for `.github/workflows/release.yml`.
- GitHub Packages is enabled for the repository.
- The tag name follows `v*.*.*`.

## Docker Image

The GHCR image entrypoint is `kestrel`; by default it runs `kestrel serve`.
Override the command for diagnostics:

```powershell
docker run --rm ghcr.io/OWNER/REPO:latest version
```
