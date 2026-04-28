"""Shared SELECT / INSERT logic for SQL-backed stores, including secret encryption."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from oratium.secrets.fernet import FernetCipher
from oratium.storage._sql_models import TenantRow
from oratium.tenant import Tenant, TenantAgentConfig, TenantSecrets


class _SQLTenantStoreBase:
    """Common implementation shared by SQLite and Postgres tenant stores.

    Subclasses set ``_engine``, ``_sessionmaker``, and (optionally)
    ``_cipher`` in ``__init__``; this base provides the four CRUD methods
    plus ``close()`` and the encrypt/decrypt round trip.

    Encryption is opt-in. If ``_cipher`` is ``None`` and a tenant being
    written has ``secrets``, ``add_tenant`` raises. If a row read back has
    ``secrets_encrypted`` set but no cipher is configured, ``_row_to_tenant``
    raises. This is fail-fast: silently dropping secrets would be a footgun.
    """

    _engine: AsyncEngine
    _sessionmaker: async_sessionmaker[AsyncSession]
    _cipher: FernetCipher | None = None

    async def add_tenant(self, tenant: Tenant) -> None:
        """Insert a tenant. Convenience for tests and bootstrapping."""
        async with self._sessionmaker() as session, session.begin():
            session.add(self._tenant_to_row(tenant))

    async def get_by_twilio_number(self, number: str) -> Tenant | None:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(TenantRow).where(TenantRow.twilio_number == number)
            )
            row = result.scalar_one_or_none()
            return self._row_to_tenant(row) if row else None

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        async with self._sessionmaker() as session:
            result = await session.execute(select(TenantRow).where(TenantRow.id == tenant_id))
            row = result.scalar_one_or_none()
            return self._row_to_tenant(row) if row else None

    async def list_all(self) -> list[Tenant]:
        async with self._sessionmaker() as session:
            result = await session.execute(select(TenantRow))
            return [self._row_to_tenant(row) for row in result.scalars().all()]

    async def close(self) -> None:
        """Dispose of the engine. Call on app shutdown."""
        await self._engine.dispose()

    # --- internal: encryption-aware Row <-> Tenant conversion ---

    def _row_to_tenant(self, row: TenantRow) -> Tenant:
        secrets: TenantSecrets | None = None
        if row.secrets_encrypted is not None:
            if self._cipher is None:
                raise RuntimeError(
                    f"Tenant {row.id!r} has encrypted secrets but no FernetCipher "
                    "is configured on this store. Pass cipher=FernetCipher.from_env() "
                    "to the store constructor."
                )
            decrypted = self._cipher.decrypt(row.secrets_encrypted)
            secrets = TenantSecrets.model_validate_json(decrypted)
        return Tenant(
            id=row.id,
            twilio_number=row.twilio_number,
            agent=TenantAgentConfig.model_validate(row.agent_config),
            secrets=secrets,
        )

    def _tenant_to_row(self, tenant: Tenant) -> TenantRow:
        secrets_encrypted: str | None = None
        if tenant.secrets is not None:
            if self._cipher is None:
                raise RuntimeError(
                    f"Cannot store tenant {tenant.id!r}: has secrets but no "
                    "FernetCipher is configured on this store."
                )
            secrets_encrypted = self._cipher.encrypt(tenant.secrets.model_dump_json())
        return TenantRow(
            id=tenant.id,
            twilio_number=tenant.twilio_number,
            agent_config=tenant.agent.model_dump(),
            secrets_encrypted=secrets_encrypted,
        )
