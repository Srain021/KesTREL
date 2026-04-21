"""Shared fixtures for domain unit tests.

Uses in-memory SQLite so each test has an isolated schema.
"""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kestrel_mcp.domain.storage import create_all, make_engine, make_sessionmaker


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    eng = make_engine()  # :memory:
    await create_all(eng)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def sm(engine: AsyncEngine) -> async_sessionmaker:
    return make_sessionmaker(engine)
