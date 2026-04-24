"""ServiceContainer — owns the DB engine + domain services for one process.

One ``ServiceContainer`` per (user machine, data directory). Multiple
engagements share the same container — they are separated at the DB row
level, not at the engine level. (Future: per-engagement SQLite files will
each get their own container; that's why the class already takes a
``database_url`` instead of touching a global.)

Construction
------------

.. code-block:: python

    container = ServiceContainer.from_url("sqlite+aiosqlite:///~/.kestrel/data.db")
    await container.initialise()  # creates tables if missing

    # per-request
    async with container.open_context(engagement_id=..., actor=...) as ctx:
        await ctx.scope.ensure(ctx.engagement_id, "x", tool_name="t")

Why a class (not module globals)
---------------------------------

* Tests can instantiate multiple containers with in-memory DBs without
  contaminating each other.
* Future SaaS mode wants one container per tenant.
* Explicit construction is easier to reason about than implicit globals.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from ..domain import entities as ent
from ..domain.services import (
    EngagementService,
    FindingService,
    ScopeService,
    TargetService,
)
from ..domain.storage import create_all, make_engine, make_sessionmaker
from ..logging import get_logger


_log = get_logger(__name__)


class ServiceContainer:
    """Wire one :class:`AsyncEngine` + one sessionmaker + every domain service."""

    def __init__(
        self,
        engine: AsyncEngine,
        sessionmaker: async_sessionmaker,
        database_url: str,
    ) -> None:
        self.engine = engine
        self.sessionmaker = sessionmaker
        self.database_url = database_url

        # Services are stateless enough to share across requests; they only
        # hold a reference to the sessionmaker.
        self.engagement = EngagementService(sessionmaker)
        self.scope = ScopeService(sessionmaker)
        self.target = TargetService(sessionmaker)
        self.finding = FindingService(sessionmaker)

    # ----- lifecycle -----

    @classmethod
    def from_url(cls, database_url: str, *, echo: bool = False) -> "ServiceContainer":
        engine = make_engine(database_url, echo=echo)
        sm = make_sessionmaker(engine)
        return cls(engine=engine, sessionmaker=sm, database_url=database_url)

    @classmethod
    def in_memory(cls) -> "ServiceContainer":
        """Shortcut for tests — single in-memory SQLite, tables created."""

        return cls.from_url("sqlite+aiosqlite:///:memory:")

    @classmethod
    def default_on_disk(cls, *, data_dir: Path | None = None) -> "ServiceContainer":
        """Default production container — single shared SQLite on disk.

        Path resolution follows :data:`KESTREL_DATA_DIR` env or XDG style:
        ``~/.kestrel/data.db``. Caller is responsible for calling
        :meth:`initialise` (or running alembic migrations) before use.
        """

        import os

        root = (data_dir or Path(os.environ.get("KESTREL_DATA_DIR", "~/.kestrel"))).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        db_file = root / "data.db"
        url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
        return cls.from_url(url)

    async def initialise(self) -> None:
        """Create all tables that don't yet exist. Idempotent."""

        await create_all(self.engine)
        _log.info("container.initialised", database_url=self.database_url)

    async def dispose(self) -> None:
        await self.engine.dispose()
        _log.info("container.disposed", database_url=self.database_url)

    # ----- context factory -----

    @asynccontextmanager
    async def open_context(
        self,
        *,
        engagement_id: UUID | None = None,
        actor: ent.Actor | None = None,
        dry_run: bool = False,
    ) -> AsyncIterator["RequestContext"]:
        """Bind a new :class:`RequestContext` for the duration of the ``with``."""

        from .context import RequestContext, bind_context  # local to avoid import cycle

        rc = RequestContext(
            container=self,
            engagement_id=engagement_id,
            actor=actor,
            dry_run=dry_run,
        )
        with bind_context(rc):
            yield rc
