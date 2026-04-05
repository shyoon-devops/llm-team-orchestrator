"""★ PoC 전용 — MCPAgentExecutor simulates an MCP-based agent for PoC.

In production, this would call an LLM with MCP tool access.
For PoC, it simulates the agent by returning mock analysis results.
"""

from __future__ import annotations

import asyncio
from typing import Any

from orchestrator.executor.base import AgentExecutor
from orchestrator.models.schemas import AgentResult


class MCPAgentExecutor(AgentExecutor):
    """Simulates an MCP-based agent (ELK analyst, Grafana analyst, etc.).

    For PoC: returns simulated analysis based on persona.
    For production: would call LLM API with MCP server tools.
    """

    def __init__(
        self,
        persona: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._persona = persona
        self._mcp_servers = mcp_servers or {}

    async def run(
        self, prompt: str, *, timeout: int = 300, context: dict[str, object] | None = None
    ) -> AgentResult:
        """Simulate MCP-based agent analysis.

        Returns a mock analysis result containing the persona and prompt summary.
        """
        await asyncio.sleep(0.05)  # simulate processing
        output = (
            f"[{self._persona}] Analysis of: {prompt[:100]}\n\nFindings: Mock analysis complete."
        )
        return AgentResult(
            output=output,
            exit_code=0,
            duration_ms=50,
            tokens_used=100,
            raw={
                "persona": self._persona,
                "mcp_servers": list(self._mcp_servers.keys()),
            },
        )

    async def health_check(self) -> bool:
        """MCP executor is always healthy in PoC mode."""
        return True

    @property
    def executor_type(self) -> str:
        return "mcp"
