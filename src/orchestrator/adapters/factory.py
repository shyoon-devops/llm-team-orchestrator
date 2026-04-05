"""Adapter factory — creates CLI adapters from YAML config."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from orchestrator.adapters.base import CLIAdapter
from orchestrator.adapters.claude import ClaudeAdapter
from orchestrator.adapters.codex import CodexAdapter
from orchestrator.adapters.gemini import GeminiAdapter
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter

if TYPE_CHECKING:
    from orchestrator.auth.key_pool import KeyPool
    from orchestrator.config.schema import AgentDef

logger = structlog.get_logger()

_CLI_MAP: dict[str, type[CLIAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
}


class AdapterFactory:
    """Creates CLIAdapter instances from config definitions.

    Falls back to MockCLIAdapter when the CLI tool is not available
    and mock_fallback is enabled.
    """

    def __init__(
        self,
        key_pool: KeyPool | None = None,
        *,
        mock_fallback: bool = True,
    ) -> None:
        self._key_pool = key_pool
        self._mock_fallback = mock_fallback

    async def create(self, name: str, agent_def: AgentDef) -> CLIAdapter:
        """Create an adapter for the given agent definition."""
        cli = agent_def.cli.lower()
        adapter_cls = _CLI_MAP.get(cli)

        # Resolve API key
        api_key = await self._resolve_key(cli)

        config = AdapterConfig(api_key=api_key, timeout=agent_def.timeout)

        if adapter_cls is None:
            if cli == "mock":
                logger.info("adapter_created", name=name, provider="mock")
                return MockCLIAdapter(config=config)
            if self._mock_fallback:
                logger.warning("adapter_fallback_mock", name=name, cli=cli)
                return MockCLIAdapter(config=config)
            msg = f"Unknown CLI tool: {cli}"
            raise ValueError(msg)

        adapter = adapter_cls(config=config)

        # Health check — fallback to mock if CLI not available
        if self._mock_fallback:
            healthy = await adapter.health_check()
            if not healthy:
                logger.warning(
                    "adapter_unhealthy_fallback",
                    name=name,
                    cli=cli,
                    reason="health_check failed, using mock",
                )
                return MockCLIAdapter(
                    config=config,
                    responses={"default": f"[Mock fallback for {cli}] Response placeholder"},
                )

        logger.info("adapter_created", name=name, provider=adapter.provider_name)
        return adapter

    async def _resolve_key(self, cli: str) -> str:
        """Resolve API key for the given CLI provider."""
        provider_map = {
            "claude": "anthropic",
            "codex": "openai",
            "gemini": "google",
        }
        provider = provider_map.get(cli, cli)

        if self._key_pool and provider in self._key_pool.providers:
            return await self._key_pool.acquire(provider)

        # Claude supports firstParty auth (no API key needed)
        if cli == "claude":
            return "firstparty"

        return ""
