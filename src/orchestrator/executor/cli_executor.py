"""CLIAgentExecutor — wraps existing CLIAdapter for backward compatibility."""

from __future__ import annotations

from orchestrator.adapters.base import CLIAdapter
from orchestrator.executor.base import AgentExecutor
from orchestrator.models.schemas import AgentResult


class CLIAgentExecutor(AgentExecutor):
    """Wraps a CLIAdapter (Claude/Codex/Gemini) as an AgentExecutor.

    This bridges the existing CLIAdapter interface to the new AgentExecutor
    abstraction, maintaining full backward compatibility with coding agents.
    """

    def __init__(self, adapter: CLIAdapter) -> None:
        self._adapter = adapter

    async def run(
        self, prompt: str, *, timeout: int = 300, context: dict[str, object] | None = None
    ) -> AgentResult:
        """Delegate to the wrapped CLIAdapter.

        Extracts ``cwd`` from context if provided.
        """
        cwd: str | None = None
        if context is not None:
            raw_cwd = context.get("cwd")
            if isinstance(raw_cwd, str):
                cwd = raw_cwd
        return await self._adapter.run(prompt, timeout=timeout, cwd=cwd)

    async def health_check(self) -> bool:
        """Delegate health check to the wrapped adapter."""
        return await self._adapter.health_check()

    @property
    def executor_type(self) -> str:
        return "cli"
