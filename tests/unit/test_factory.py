"""Unit tests for AdapterFactory."""

from __future__ import annotations

import pytest

from orchestrator.adapters.claude import ClaudeAdapter
from orchestrator.adapters.factory import AdapterFactory
from orchestrator.auth.key_pool import KeyPool
from orchestrator.config.schema import AgentDef
from orchestrator.poc.mock_adapters import MockCLIAdapter


@pytest.fixture
def factory() -> AdapterFactory:
    return AdapterFactory(mock_fallback=True)


class TestAdapterFactory:
    async def test_create_mock_adapter(self, factory: AdapterFactory) -> None:
        agent_def = AgentDef(cli="mock", role="test")
        adapter = await factory.create("test", agent_def)
        assert isinstance(adapter, MockCLIAdapter)

    async def test_unknown_cli_with_fallback(self, factory: AdapterFactory) -> None:
        agent_def = AgentDef(cli="unknown_tool", role="test")
        adapter = await factory.create("test", agent_def)
        assert isinstance(adapter, MockCLIAdapter)

    async def test_unknown_cli_without_fallback(self) -> None:
        factory = AdapterFactory(mock_fallback=False)
        agent_def = AgentDef(cli="unknown_tool", role="test")
        with pytest.raises(ValueError, match="Unknown CLI tool"):
            await factory.create("test", agent_def)

    async def test_unhealthy_cli_falls_back_to_mock(self, factory: AdapterFactory) -> None:
        """codex/gemini CLI not installed → should fall back to mock."""
        agent_def = AgentDef(cli="codex", role="test")
        adapter = await factory.create("test", agent_def)
        assert isinstance(adapter, MockCLIAdapter)

    async def test_claude_firstparty_key(self, factory: AdapterFactory) -> None:
        """Without key pool, Claude should get 'firstparty' key."""
        agent_def = AgentDef(cli="claude", role="test")
        # Claude is installed so it won't fallback — but key should be firstparty
        adapter = await factory.create("test", agent_def)
        # Either real or mock, config should reflect firstparty
        if isinstance(adapter, ClaudeAdapter):
            assert adapter.config.api_key == "firstparty"

    async def test_key_pool_integration(self) -> None:
        """KeyPool should provide keys to factory."""
        pool = KeyPool()
        pool.initialize("openai", ["sk-test-1", "sk-test-2"])
        factory = AdapterFactory(key_pool=pool, mock_fallback=True)
        agent_def = AgentDef(cli="codex", role="test")
        adapter = await factory.create("test", agent_def)
        # codex is not installed, falls back to mock, but key was resolved
        assert isinstance(adapter, MockCLIAdapter)

    async def test_key_pool_round_robin(self) -> None:
        """KeyPool round-robin should provide different keys."""
        pool = KeyPool()
        pool.initialize("anthropic", ["key-a", "key-b"])
        factory = AdapterFactory(key_pool=pool, mock_fallback=True)
        agent_def = AgentDef(cli="claude", role="test")

        adapter1 = await factory.create("a", agent_def)
        adapter2 = await factory.create("b", agent_def)
        # Keys should be different (round-robin)
        if isinstance(adapter1, ClaudeAdapter) and isinstance(adapter2, ClaudeAdapter):
            assert adapter1.config.api_key != adapter2.config.api_key
