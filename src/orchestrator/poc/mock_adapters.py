"""★ PoC 전용 — MVP 전환 시 제거

Mock CLI adapters for testing the graph without real CLI tools.
"""

from __future__ import annotations

import asyncio

from orchestrator.adapters.base import CLIAdapter
from orchestrator.errors.exceptions import CLIExecutionError, CLITimeoutError
from orchestrator.models.schemas import AdapterConfig, AgentResult


class MockCLIAdapter(CLIAdapter):
    """Mock adapter that returns pre-configured responses."""

    def __init__(
        self,
        config: AdapterConfig,
        responses: dict[str, str] | None = None,
        *,
        fail_on: set[str] | None = None,
        latency_ms: int = 100,
    ) -> None:
        super().__init__(config)
        self.responses = responses or {}
        self.fail_on = fail_on or set()
        self.latency_ms = latency_ms
        self.call_log: list[str] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    async def run(
        self, prompt: str, *, timeout: int = 300, cwd: str | None = None
    ) -> AgentResult:
        self.call_log.append(prompt)

        # Simulate latency
        await asyncio.sleep(self.latency_ms / 1000)

        # Simulate failures
        if "timeout" in self.fail_on and "timeout" in prompt.lower():
            raise CLITimeoutError("Mock timeout")
        if "error" in self.fail_on and "error" in prompt.lower():
            raise CLIExecutionError("Mock execution error")

        output = self.responses.get("default", f"Mock response for: {prompt[:80]}")
        return AgentResult(
            output=output,
            exit_code=0,
            duration_ms=self.latency_ms,
            tokens_used=50,
            raw={},
        )

    async def health_check(self) -> bool:
        return True


class FailingMockAdapter(CLIAdapter):
    """Mock adapter that always fails — for testing error handling."""

    def __init__(self, config: AdapterConfig, error_message: str = "Simulated failure") -> None:
        super().__init__(config)
        self.error_message = error_message

    @property
    def provider_name(self) -> str:
        return "mock-failing"

    async def run(
        self, prompt: str, *, timeout: int = 300, cwd: str | None = None
    ) -> AgentResult:
        raise CLIExecutionError(self.error_message)

    async def health_check(self) -> bool:
        return False
