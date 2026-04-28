"""TenantStore protocol — backend-agnostic interface for tenant configuration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from oratium.tenant import Tenant


@runtime_checkable
class TenantStore(Protocol):
    """Backend-agnostic interface for tenant configuration storage.

    All methods are async even when the backend is in-memory (YAML), so the
    OratiumApp websocket handler has one signature to call regardless of
    backend.
    """

    async def get_by_twilio_number(self, number: str) -> Tenant | None:
        """Fetch a tenant by their assigned Twilio number (E.164)."""
        ...

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        """Fetch a tenant by id."""
        ...

    async def list_all(self) -> list[Tenant]:
        """Return all tenants. Intended for admin / debugging — not the call hot path."""
        ...
