"""Postgres tenant store. Suitable for production / multi-node deployments."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oratium.secrets.fernet import FernetCipher
from oratium.storage._sql_base import _SQLTenantStoreBase


class PostgresTenantStore(_SQLTenantStoreBase):
    """Postgres-backed tenant store using ``asyncpg``.

    Schema is managed by Alembic migrations shipped with oratium. Run
    ``alembic upgrade head`` once on first boot and again after each
    upgrade.

    The DSN is normalized to use the asyncpg driver, so any of these forms
    work as input::

        postgres://user:pass@host:5432/db
        postgresql://user:pass@host:5432/db
        postgresql+asyncpg://user:pass@host:5432/db

    Pass a :class:`FernetCipher` if any tenant will have secrets.
    """

    def __init__(
        self,
        dsn: str,
        *,
        cipher: FernetCipher | None = None,
    ) -> None:
        normalized = self._normalize_dsn(dsn)
        self._engine = create_async_engine(normalized, echo=False, future=True)
        self._sessionmaker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cipher = cipher

    @staticmethod
    def _normalize_dsn(dsn: str) -> str:
        if dsn.startswith("postgresql+asyncpg://"):
            return dsn
        if dsn.startswith("postgres://"):
            dsn = "postgresql://" + dsn[len("postgres://") :]
        if dsn.startswith("postgresql://"):
            return "postgresql+asyncpg://" + dsn[len("postgresql://") :]
        raise ValueError(f"Unsupported Postgres DSN scheme: {dsn!r}")
