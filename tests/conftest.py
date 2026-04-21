"""Shared pytest fixtures.

We scrub any ``KESTREL_MCP_*`` env var in the session fixture so tests are
deterministic regardless of what the developer exported in their shell.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("KESTREL_MCP_"):
            monkeypatch.delenv(key, raising=False)
