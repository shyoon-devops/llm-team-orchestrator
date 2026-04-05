"""Agent executor abstraction — domain-agnostic agent execution interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from orchestrator.models.schemas import AgentResult


class AgentExecutor(ABC):
    """Universal agent execution interface.

    Implementations:
    - CLIAgentExecutor: wraps CLIAdapter for coding agents (subprocess)
    - MCPAgentExecutor: runs LLM + MCP tool calls for general agents (in-process)
    - MockAgentExecutor: for testing
    """

    @abstractmethod
    async def run(
        self, prompt: str, *, timeout: int = 300, context: dict[str, object] | None = None
    ) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: The prompt/task to execute.
            timeout: Timeout in seconds.
            context: Optional execution context (e.g., cwd, env vars).
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the executor is ready to process tasks."""
        ...

    @property
    @abstractmethod
    def executor_type(self) -> str:
        """Executor type identifier: 'cli' | 'mcp' | 'mock'."""
        ...
