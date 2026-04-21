"""Shared plumbing for all domain services."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...logging import get_logger
from ..storage import open_session


class _ServiceBase:
    """Abstract base: every service needs a sessionmaker and a logger."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = sessionmaker
        self.log = get_logger(f"domain.{type(self).__name__}")

    def _session(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Return an ``async with`` context opening a committing session."""

        return open_session(self._sm)
