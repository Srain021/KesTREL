"""Path traversal defence helpers.

Route user- or LLM-supplied file paths through :func:`safe_path` before using
them for filesystem writes. The helper guarantees the resolved path remains
under a declared root, mitigating THREAT T-E3.
"""

from __future__ import annotations

from pathlib import Path

from ..core_errors import UserInputError


class PathTraversalError(UserInputError):
    """Raised when a supplied path would escape the declared base directory."""

    error_code = "kestrel.path_traversal"


def safe_path(base: Path | str, user_input: str) -> Path:
    """Join ``user_input`` under ``base`` and refuse escapes.

    ``base`` must already exist and be a directory. Absolute inputs are
    rejected before joining, and the final resolved path must still be inside
    ``base``.
    """

    base_path = Path(base).resolve(strict=False)
    if not base_path.exists() or not base_path.is_dir():
        raise PathTraversalError(
            f"safe_path base does not exist or is not a directory: {base_path}"
        )

    candidate_raw = str(user_input or "").strip()
    if not candidate_raw:
        raise PathTraversalError("safe_path user_input is empty")
    if _looks_absolute(candidate_raw):
        raise PathTraversalError(f"safe_path absolute user input refused: {candidate_raw!r}")

    joined = (base_path / candidate_raw).resolve(strict=False)
    try:
        joined.relative_to(base_path)
    except ValueError as exc:
        raise PathTraversalError(
            f"safe_path input {candidate_raw!r} escapes base {base_path}"
        ) from exc

    return joined


def _looks_absolute(value: str) -> bool:
    if value.startswith(("/", "\\")):
        return True
    if len(value) >= 2 and value[1] == ":":
        return True
    return value.startswith("//") or value.startswith("\\\\")


__all__ = ["PathTraversalError", "safe_path"]
