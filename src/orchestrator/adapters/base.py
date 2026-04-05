"""CLI adapter abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from orchestrator.models.schemas import AdapterConfig, AgentResult


class CLIAdapter(ABC):
    """Abstract interface for CLI tool integration."""

    def __init__(self, config: AdapterConfig) -> None:
        self.config = config

    @abstractmethod
    async def run(
        self, prompt: str, *, timeout: int = 300, cwd: str | None = None
    ) -> AgentResult:
        """Send a prompt to the CLI tool and return the result.

        Args:
            prompt: The prompt to send.
            timeout: Timeout in seconds.
            cwd: Working directory for the CLI subprocess.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the CLI tool is available."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (anthropic, openai, google)."""
        ...
