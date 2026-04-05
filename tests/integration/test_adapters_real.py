"""Integration tests — real CLI invocations for all adapters.  ★ PoC 전용

Requires: claude, codex, gemini CLIs installed and authenticated.
Run with: uv run pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import pytest

from orchestrator.adapters.claude import ClaudeAdapter
from orchestrator.adapters.codex import CodexAdapter
from orchestrator.adapters.gemini import GeminiAdapter
from orchestrator.models.schemas import AdapterConfig


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Codex
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestCodexAdapterReal:
    async def test_health_check(self) -> None:
        config = AdapterConfig(timeout=30)
        adapter = CodexAdapter(config=config)
        result = await adapter.health_check()
        assert result is True

    async def test_simple_prompt(self) -> None:
        """Call Codex CLI with a minimal prompt and verify response structure."""
        config = AdapterConfig(timeout=120)
        adapter = CodexAdapter(config=config)

        result = await adapter.run(
            "Respond with exactly one word: hello_codex",
            timeout=120,
        )

        assert result.exit_code == 0
        assert result.success is True
        assert len(result.output) > 0
        assert result.tokens_used > 0
        assert result.raw is not None

    async def test_provider_name(self) -> None:
        config = AdapterConfig(timeout=30)
        adapter = CodexAdapter(config=config)
        assert adapter.provider_name == "openai"


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestGeminiAdapterReal:
    async def test_health_check(self) -> None:
        config = AdapterConfig(timeout=30)
        adapter = GeminiAdapter(config=config)
        result = await adapter.health_check()
        assert result is True

    async def test_simple_prompt(self) -> None:
        """Call Gemini CLI with a minimal prompt and verify response structure."""
        config = AdapterConfig(timeout=120)
        adapter = GeminiAdapter(config=config)

        result = await adapter.run(
            "Respond with exactly one word: hello_gemini",
            timeout=120,
        )

        assert result.exit_code == 0
        assert result.success is True
        assert len(result.output) > 0
        assert result.tokens_used > 0
        assert result.duration_ms > 0
        assert result.raw is not None

    async def test_provider_name(self) -> None:
        config = AdapterConfig(timeout=30)
        adapter = GeminiAdapter(config=config)
        assert adapter.provider_name == "google"
