"""Unit tests for key pool."""

import pytest

from orchestrator.auth.key_pool import KeyPool
from orchestrator.errors.exceptions import AuthError


class TestKeyPool:
    def test_initialize(self) -> None:
        pool = KeyPool()
        pool.initialize("anthropic", ["key1", "key2"])
        assert pool.pool_size("anthropic") == 2

    def test_initialize_empty_raises(self) -> None:
        pool = KeyPool()
        with pytest.raises(AuthError, match="empty"):
            pool.initialize("anthropic", [])

    async def test_acquire_round_robin(self) -> None:
        pool = KeyPool()
        pool.initialize("anthropic", ["key1", "key2", "key3"])

        keys = [await pool.acquire("anthropic") for _ in range(6)]
        assert keys == ["key1", "key2", "key3", "key1", "key2", "key3"]

    async def test_acquire_uninitialized(self) -> None:
        pool = KeyPool()
        with pytest.raises(AuthError, match="not initialized"):
            await pool.acquire("unknown")

    async def test_mark_exhausted(self) -> None:
        pool = KeyPool()
        pool.initialize("anthropic", ["key1", "key2"])
        await pool.mark_exhausted("anthropic", "key1")
        assert pool.pool_size("anthropic") == 1

        key = await pool.acquire("anthropic")
        assert key == "key2"

    async def test_all_exhausted(self) -> None:
        pool = KeyPool()
        pool.initialize("anthropic", ["key1"])
        await pool.mark_exhausted("anthropic", "key1")
        with pytest.raises(AuthError, match="exhausted"):
            await pool.acquire("anthropic")

    def test_providers(self) -> None:
        pool = KeyPool()
        pool.initialize("anthropic", ["k1"])
        pool.initialize("openai", ["k2"])
        assert set(pool.providers) == {"anthropic", "openai"}
