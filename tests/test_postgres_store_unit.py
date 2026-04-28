"""Unit tests for PostgresTenantStore — only the bits that don't need a real DB.

A full integration test against a live Postgres lives outside Phase 2's scope
(would require pytest-postgresql or a docker-compose service in CI). The DSN
normalization is the critical bit users hit on first install.
"""

from __future__ import annotations

import pytest

from oratium.storage.postgres import PostgresTenantStore


@pytest.mark.parametrize(
    ("input_dsn", "expected_prefix"),
    [
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
    ],
)
def test_dsn_is_normalized_to_asyncpg(input_dsn: str, expected_prefix: str) -> None:
    assert PostgresTenantStore._normalize_dsn(input_dsn) == expected_prefix


def test_unsupported_dsn_scheme_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported Postgres DSN scheme"):
        PostgresTenantStore._normalize_dsn("mysql://u:p@h:3306/db")


def test_construct_does_not_connect() -> None:
    """create_async_engine is lazy — construction must not require a live DB."""
    store = PostgresTenantStore("postgresql://nobody@127.0.0.1:1/none")
    assert store is not None
