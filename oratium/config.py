"""Configuration helpers — pick a TenantStore backend from environment variables."""

from __future__ import annotations

import os

from oratium.storage.base import TenantStore


def tenant_store_from_env() -> TenantStore | None:
    """Resolve a :class:`TenantStore` from environment variables.

    Resolution order (first match wins):

    1. ``DATABASE_URL`` starting with ``postgres://`` / ``postgresql://`` →
       :class:`PostgresTenantStore`.
    2. ``DATABASE_URL`` starting with ``sqlite`` →
       :class:`SQLiteTenantStore` (path parsed from URL).
    3. ``ORATIUM_TENANTS_FILE`` set → :class:`YAMLTenantStore` at that path.
    4. ``ORATIUM_SQLITE_PATH`` set → :class:`SQLiteTenantStore` at that path.
    5. None of the above → returns ``None``. Caller falls back to
       single-tenant mode (``OratiumApp(agent=...)``) or raises.
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if db_url.startswith(("postgres://", "postgresql://", "postgresql+")):
            from oratium.storage.postgres import PostgresTenantStore

            return PostgresTenantStore(db_url)
        if db_url.startswith("sqlite"):
            from oratium.storage.sqlite import SQLiteTenantStore

            path = db_url.split("///", 1)[1] if "///" in db_url else None
            return SQLiteTenantStore(path or None)

    yaml_path = os.environ.get("ORATIUM_TENANTS_FILE")
    if yaml_path:
        from oratium.storage.yaml_store import YAMLTenantStore

        return YAMLTenantStore(yaml_path)

    sqlite_path = os.environ.get("ORATIUM_SQLITE_PATH")
    if sqlite_path:
        from oratium.storage.sqlite import SQLiteTenantStore

        return SQLiteTenantStore(sqlite_path)

    return None
