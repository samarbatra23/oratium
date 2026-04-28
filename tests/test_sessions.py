from __future__ import annotations

import asyncio

from oratium.storage.sessions import InMemorySessionStore, RedisSessionStore, SessionStore


def test_in_memory_implements_protocol() -> None:
    store = InMemorySessionStore()
    assert isinstance(store, SessionStore)


def test_redis_implements_protocol() -> None:
    store = RedisSessionStore("redis://localhost:6379/0")
    assert isinstance(store, SessionStore)


async def test_set_then_get() -> None:
    store = InMemorySessionStore()
    await store.set("call:abc", "state-1", ttl_seconds=60)
    assert await store.get("call:abc") == "state-1"


async def test_get_missing_returns_none() -> None:
    store = InMemorySessionStore()
    assert await store.get("nope") is None


async def test_set_overwrites() -> None:
    store = InMemorySessionStore()
    await store.set("k", "v1", ttl_seconds=60)
    await store.set("k", "v2", ttl_seconds=60)
    assert await store.get("k") == "v2"


async def test_delete_removes_key() -> None:
    store = InMemorySessionStore()
    await store.set("k", "v", ttl_seconds=60)
    await store.delete("k")
    assert await store.get("k") is None


async def test_delete_missing_is_noop() -> None:
    store = InMemorySessionStore()
    await store.delete("ghost")  # must not raise


async def test_ttl_expires_value() -> None:
    store = InMemorySessionStore()
    # Use a tiny TTL and sleep just past it.
    await store.set("k", "v", ttl_seconds=0)
    await asyncio.sleep(0.01)
    assert await store.get("k") is None


async def test_ttl_per_key() -> None:
    store = InMemorySessionStore()
    await store.set("short", "x", ttl_seconds=0)
    await store.set("long", "y", ttl_seconds=60)
    await asyncio.sleep(0.01)
    assert await store.get("short") is None
    assert await store.get("long") == "y"
