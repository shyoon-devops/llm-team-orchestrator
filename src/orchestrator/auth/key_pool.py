"""API key pool with round-robin and cooldown."""

from __future__ import annotations

import asyncio

import structlog

from orchestrator.errors.exceptions import AuthError

logger = structlog.get_logger()


class KeyPool:
    """Round-robin API key pool with exhaustion handling."""

    def __init__(self) -> None:
        self._pools: dict[str, list[str]] = {}
        self._index: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def initialize(self, provider: str, keys: list[str]) -> None:
        if not keys:
            raise AuthError(f"Cannot initialize empty key pool for: {provider}")
        self._pools[provider] = list(keys)
        self._index[provider] = 0
        self._locks[provider] = asyncio.Lock()
        logger.info("key_pool_initialized", provider=provider, key_count=len(keys))

    async def acquire(self, provider: str) -> str:
        lock = self._locks.get(provider)
        if lock is None:
            raise AuthError(f"Key pool not initialized for: {provider}")
        async with lock:
            pool = self._pools.get(provider, [])
            if not pool:
                raise AuthError(f"All keys exhausted for: {provider}")
            idx = self._index[provider] % len(pool)
            self._index[provider] += 1
            return pool[idx]

    async def mark_exhausted(self, provider: str, key: str) -> None:
        lock = self._locks.get(provider)
        if lock is None:
            return
        async with lock:
            pool = self._pools.get(provider, [])
            if key in pool:
                pool.remove(key)
                logger.warning("key_exhausted", provider=provider, remaining=len(pool))

    def pool_size(self, provider: str) -> int:
        return len(self._pools.get(provider, []))

    @property
    def providers(self) -> list[str]:
        return [p for p, keys in self._pools.items() if keys]
