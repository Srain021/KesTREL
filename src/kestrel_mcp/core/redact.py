"""Best-effort sensitive string redaction.

This is intentionally small and dependency-free, not a full DLP engine. Its
job is to keep common tokens, hashes, passwords, and private keys out of logs
and subprocess stderr. More exhaustive policy belongs in a later hardening RFC.
"""

from __future__ import annotations

import re
from typing import overload

_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "<PRIVATE_KEY_REDACTED>",
    ),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{8,}"), "Bearer <REDACTED>"),
    (re.compile(r"(?im)^\s*Authorization\s*:\s*.+$"), "Authorization: <REDACTED>"),
    (
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?key)\s*[=:]\s*"
            r"[\"']?[A-Za-z0-9._\-+/]{8,}[\"']?"
        ),
        r"\1=<REDACTED>",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
        "<JWT_REDACTED>",
    ),
    (re.compile(r"\b[a-fA-F0-9]{32}:[a-fA-F0-9]{32}\b"), "<NTLM_HASH_PAIR_REDACTED>"),
    (re.compile(r"(?i)password\s*[=:]\s*[\"']?\S+[\"']?"), "password=<REDACTED>"),
]


@overload
def redact(text: str) -> str: ...


@overload
def redact(text: None) -> None: ...


def redact(text: str | None) -> str | None:
    """Apply every redaction rule in sequence."""

    if not text:
        return text
    redacted = text
    for pattern, replacement in _RULES:
        redacted = pattern.sub(replacement, redacted)
    return redacted


__all__ = ["redact"]
