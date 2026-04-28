"""Session storage — per-call state with TTL.

Two implementations:

* :class:`InMemorySessionStore` — single-process, dev / tests.
* :class:`RedisSessionStore` — multi-process production via ``redis.asyncio``.

The module is named ``sessions`` rather than ``redis`` so that
``oratium.storage.redis`` does not shadow the ``redis`` package import.
See decision 0006 in ``docs/architecture.md``.

Phase 3 establishes the primitive. Phase 5's reliability work plugs in
actual usage (call-state recovery on reconnect, fallback context, per-call
rate limiting).
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol, runtime_checkable

import redis.asyncio


@runtime_checkable
class SessionStore(Protocol):
    """Backend-agnostic key-value session store with TTL on writes."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None: ...

    async def delete(self, key: str) -> None: ...


class InMemorySessionStore:
    """Process-local session store. Single-process dev and test only.

    Not safe across multiple oratium replicas. Use
    :class:`RedisSessionStore` for production.
    """

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() >= expires_at:
                del self._data[key]
                return None
            return value

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        async with self._lock:
            self._data[key] = (value, time.monotonic() + ttl_seconds)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)


class RedisSessionStore:
    """Redis-backed session store using ``redis.asyncio``.

    Suitable for production / multi-node deployments. Pass a Redis URL
    (``redis://host:6379/0``); auth and TLS belong in the URL.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._redis = redis.asyncio.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        result = await self._redis.get(key)
        return result if result is None else str(result)

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        await self._redis.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def close(self) -> None:
        """Close the connection pool. Call on shutdown."""
        await self._redis.aclose()
