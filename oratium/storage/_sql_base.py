"""Shared SELECT / INSERT logic for SQL-backed stores."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from oratium.storage._sql_models import TenantRow
from oratium.tenant import Tenant


class _SQLTenantStoreBase:
    """Common implementation shared by SQLite and Postgres tenant stores.

    Subclasses set ``_engine`` and ``_sessionmaker`` in ``__init__``; this
    base provides the four CRUD methods plus ``close()``.
    """

    _engine: AsyncEngine
    _sessionmaker: async_sessionmaker[AsyncSession]

    async def add_tenant(self, tenant: Tenant) -> None:
        """Insert a tenant. Convenience for tests and bootstrapping."""
        async with self._sessionmaker() as session, session.begin():
            session.add(TenantRow.from_pydantic(tenant))

    async def get_by_twilio_number(self, number: str) -> Tenant | None:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(TenantRow).where(TenantRow.twilio_number == number)
            )
            row = result.scalar_one_or_none()
            return row.to_pydantic() if row else None

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        async with self._sessionmaker() as session:
            result = await session.execute(select(TenantRow).where(TenantRow.id == tenant_id))
            row = result.scalar_one_or_none()
            return row.to_pydantic() if row else None

    async def list_all(self) -> list[Tenant]:
        async with self._sessionmaker() as session:
            result = await session.execute(select(TenantRow))
            return [row.to_pydantic() for row in result.scalars().all()]

    async def close(self) -> None:
        """Dispose of the engine. Call on app shutdown."""
        await self._engine.dispose()
