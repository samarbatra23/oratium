"""SQLite tenant store. Suitable for dev and single-node deployments."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oratium.storage._sql_base import _SQLTenantStoreBase
from oratium.storage._sql_models import Base


class SQLiteTenantStore(_SQLTenantStoreBase):
    """SQLite-backed tenant store using ``aiosqlite``.

    No migrations: the schema is created on first :meth:`initialize` call.
    For Postgres deployments where the schema needs to evolve safely, use
    :class:`PostgresTenantStore` and the ``oratium-migrate`` CLI.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        url = "sqlite+aiosqlite:///:memory:" if path is None else f"sqlite+aiosqlite:///{path}"
        self._engine = create_async_engine(url, echo=False, future=True)
        self._sessionmaker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def initialize(self) -> None:
        """Create the tenants table if it doesn't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
