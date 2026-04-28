from __future__ import annotations

import pytest

from oratium.storage.sqlite import SQLiteTenantStore
from oratium.tenant import Tenant, TenantAgentConfig


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
