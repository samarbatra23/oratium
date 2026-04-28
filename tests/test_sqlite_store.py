from __future__ import annotations

import pytest

from oratium.secrets.fernet import FernetCipher
from oratium.storage.sqlite import SQLiteTenantStore
from oratium.tenant import Tenant, TenantAgentConfig, TenantSecrets


def _make_tenant(
    tid: str = "t1",
    number: str = "+15555550100",
    name: str = "Hello",
    voice: str = "alloy",
) -> Tenant:
    return Tenant(
        id=tid,
        twilio_number=number,
        agent=TenantAgentConfig(name=name, voice=voice, instructions="x"),
    )


@pytest.fixture
async def store() -> SQLiteTenantStore:
    s = SQLiteTenantStore()  # in-memory
    await s.initialize()
    return s


async def test_initialize_is_idempotent() -> None:
    s = SQLiteTenantStore()
    await s.initialize()
    await s.initialize()  # second call must not raise
    await s.close()


async def test_add_and_get_by_twilio_number(store: SQLiteTenantStore) -> None:
    await store.add_tenant(_make_tenant())
    tenant = await store.get_by_twilio_number("+15555550100")
    assert tenant is not None
    assert tenant.id == "t1"
    assert tenant.agent.name == "Hello"
    await store.close()


async def test_add_and_get_by_id(store: SQLiteTenantStore) -> None:
    await store.add_tenant(_make_tenant(tid="abc"))
    tenant = await store.get_by_id("abc")
    assert tenant is not None
    assert tenant.twilio_number == "+15555550100"
    await store.close()


async def test_get_misses_return_none(store: SQLiteTenantStore) -> None:
    assert await store.get_by_twilio_number("+15555550999") is None
    assert await store.get_by_id("ghost") is None
    await store.close()


async def test_list_all_returns_inserted_tenants(store: SQLiteTenantStore) -> None:
    await store.add_tenant(_make_tenant(tid="a", number="+15555550101"))
    await store.add_tenant(_make_tenant(tid="b", number="+15555550102"))
    tenants = await store.list_all()
    assert {t.id for t in tenants} == {"a", "b"}
    await store.close()


async def test_round_trip_preserves_agent_config(store: SQLiteTenantStore) -> None:
    original = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(
            name="Roundtrip",
            instructions="Be brief.",
            voice="verse",
            model="custom-model-id",
        ),
    )
    await store.add_tenant(original)
    fetched = await store.get_by_id("t1")
    assert fetched == original
    await store.close()


# --- secrets encryption ---


async def test_tenant_without_secrets_does_not_require_cipher() -> None:
    store = SQLiteTenantStore()  # no cipher
    await store.initialize()
    tenant = _make_tenant()
    await store.add_tenant(tenant)
    fetched = await store.get_by_id(tenant.id)
    assert fetched == tenant
    await store.close()


async def test_secrets_round_trip_through_encryption() -> None:
    cipher = FernetCipher(FernetCipher.generate_key())
    store = SQLiteTenantStore(cipher=cipher)
    await store.initialize()
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
        secrets=TenantSecrets(openai_api_key="sk-secret-tenant-key"),
    )
    await store.add_tenant(tenant)
    fetched = await store.get_by_id("t1")
    assert fetched is not None
    assert fetched.secrets is not None
    assert fetched.secrets.openai_api_key == "sk-secret-tenant-key"
    await store.close()


async def test_writing_secrets_without_cipher_raises() -> None:
    store = SQLiteTenantStore()  # no cipher
    await store.initialize()
    tenant = Tenant(
        id="t1",
        twilio_number="+15555550100",
        agent=TenantAgentConfig(name="x"),
        secrets=TenantSecrets(openai_api_key="sk-x"),
    )
    with pytest.raises(RuntimeError, match="no FernetCipher"):
        await store.add_tenant(tenant)
    await store.close()


async def test_persisted_secrets_need_matching_key(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Same DB file written with cipher A, read with cipher B — must raise InvalidToken."""
    from pathlib import Path

    from cryptography.fernet import InvalidToken

    path = Path(str(tmp_path)) / "tenants.sqlite"
    cipher_a = FernetCipher(FernetCipher.generate_key())
    cipher_b = FernetCipher(FernetCipher.generate_key())

    store_a = SQLiteTenantStore(path=path, cipher=cipher_a)
    await store_a.initialize()
    await store_a.add_tenant(
        Tenant(
            id="t1",
            twilio_number="+15555550100",
            agent=TenantAgentConfig(name="x"),
            secrets=TenantSecrets(openai_api_key="sk-x"),
        )
    )
    await store_a.close()

    store_b = SQLiteTenantStore(path=path, cipher=cipher_b)
    with pytest.raises(InvalidToken):
        await store_b.get_by_id("t1")
    await store_b.close()


async def test_persisted_secrets_unreadable_without_cipher() -> None:
    """Same DB file written with a cipher, read by a store without one — must raise."""
    import tempfile
    from pathlib import Path

    cipher = FernetCipher(FernetCipher.generate_key())
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "tenants.sqlite"

        store_with = SQLiteTenantStore(path=path, cipher=cipher)
        await store_with.initialize()
        tenant = Tenant(
            id="t1",
            twilio_number="+15555550100",
            agent=TenantAgentConfig(name="x"),
            secrets=TenantSecrets(openai_api_key="sk-x"),
        )
        await store_with.add_tenant(tenant)
        await store_with.close()

        store_without = SQLiteTenantStore(path=path)  # no cipher
        with pytest.raises(RuntimeError, match="no FernetCipher"):
            await store_without.get_by_id("t1")
        await store_without.close()
