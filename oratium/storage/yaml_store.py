"""YAML file-backed tenant store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from oratium.tenant import Tenant


class YAMLTenantStore:
    """In-memory tenant store backed by a YAML file.

    Loads at construction time and caches in memory. Suitable for dev or
    small deployments where tenants change infrequently and a redeploy is
    acceptable. For dynamic updates, use :class:`SQLiteTenantStore` or
    :class:`PostgresTenantStore`.

    Expected file shape::

        tenants:
          - id: example-1
            twilio_number: "+15555550100"
            agent:
              name: Example Agent
              instructions: |
                You are...
              voice: alloy
              model: gpt-realtime
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._by_id: dict[str, Tenant] = {}
        self._by_number: dict[str, Tenant] = {}
        self._load()

    def _load(self) -> None:
        with self._path.open() as f:
            data: Any = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{self._path}: top-level must be a mapping")
        entries = data.get("tenants", [])
        if not isinstance(entries, list):
            raise ValueError(f"{self._path}: 'tenants' must be a list")
        for entry in entries:
            tenant = Tenant.model_validate(entry)
            if tenant.id in self._by_id:
                raise ValueError(f"Duplicate tenant id: {tenant.id}")
            if tenant.twilio_number in self._by_number:
                raise ValueError(f"Duplicate Twilio number: {tenant.twilio_number}")
            self._by_id[tenant.id] = tenant
            self._by_number[tenant.twilio_number] = tenant

    async def get_by_twilio_number(self, number: str) -> Tenant | None:
        return self._by_number.get(number)

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        return self._by_id.get(tenant_id)

    async def list_all(self) -> list[Tenant]:
        return list(self._by_id.values())
