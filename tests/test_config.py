from __future__ import annotations

from pathlib import Path

import pytest

from oratium.config import tenant_store_from_env
from oratium.storage.postgres import PostgresTenantStore
from oratium.storage.sqlite import SQLiteTenantStore
from oratium.storage.yaml_store import YAMLTenantStore


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test starts with a clean env for the resolution-order checks."""
    for var in ("DATABASE_URL", "ORATIUM_TENANTS_FILE", "ORATIUM_SQLITE_PATH"):
        monkeypatch.delenv(var, raising=False)


def test_returns_none_when_nothing_configured() -> None:
    assert tenant_store_from_env() is None


def test_database_url_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
    store = tenant_store_from_env()
    assert isinstance(store, PostgresTenantStore)


def test_database_url_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    store = tenant_store_from_env()
    assert isinstance(store, PostgresTenantStore)


def test_database_url_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "x.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    store = tenant_store_from_env()
    assert isinstance(store, SQLiteTenantStore)


def test_database_url_takes_precedence_over_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    yaml_path = tmp_path / "tenants.yaml"
    yaml_path.write_text("tenants: []\n")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
    monkeypatch.setenv("ORATIUM_TENANTS_FILE", str(yaml_path))
    store = tenant_store_from_env()
    assert isinstance(store, PostgresTenantStore)


def test_yaml_file_when_no_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = tmp_path / "tenants.yaml"
    yaml_path.write_text("tenants: []\n")
    monkeypatch.setenv("ORATIUM_TENANTS_FILE", str(yaml_path))
    store = tenant_store_from_env()
    assert isinstance(store, YAMLTenantStore)


def test_yaml_takes_precedence_over_sqlite_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    yaml_path = tmp_path / "tenants.yaml"
    yaml_path.write_text("tenants: []\n")
    monkeypatch.setenv("ORATIUM_TENANTS_FILE", str(yaml_path))
    monkeypatch.setenv("ORATIUM_SQLITE_PATH", str(tmp_path / "ignored.sqlite"))
    store = tenant_store_from_env()
    assert isinstance(store, YAMLTenantStore)


def test_sqlite_path_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORATIUM_SQLITE_PATH", str(tmp_path / "x.sqlite"))
    store = tenant_store_from_env()
    assert isinstance(store, SQLiteTenantStore)
