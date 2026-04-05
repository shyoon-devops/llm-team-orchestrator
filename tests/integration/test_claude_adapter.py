"""Integration test — real Claude Code CLI invocation.

Requires: claude CLI installed and authenticated.
Run with: uv run pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import pytest

from orchestrator.adapters.claude import ClaudeAdapter
from orchestrator.models.schemas import AdapterConfig


@pytest.mark.integration
class TestClaudeAdapterReal:
    async def test_health_check(self) -> None:
        config = AdapterConfig(api_key="firstparty", timeout=30)
        adapter = ClaudeAdapter(config=config)
        result = await adapter.health_check()
        assert result is True

    async def test_simple_prompt(self) -> None:
        """Call Claude CLI with a minimal prompt and verify response structure."""
        config = AdapterConfig(api_key="firstparty", timeout=60)
        adapter = ClaudeAdapter(config=config)

        result = await adapter.run(
            "Respond with exactly one word: hello",
            timeout=60,
        )

        assert result.exit_code == 0
        assert result.success is True
        assert len(result.output) > 0
        assert result.duration_ms > 0
        assert result.tokens_used > 0
        assert result.raw is not None
        assert result.raw.get("type") == "result"

    async def test_provider_name(self) -> None:
        config = AdapterConfig(api_key="firstparty", timeout=30)
        adapter = ClaudeAdapter(config=config)
        assert adapter.provider_name == "anthropic"
