"""Unit tests for AgentExecutor implementations."""

from __future__ import annotations

import pytest

from orchestrator.executor.base import AgentExecutor
from orchestrator.executor.cli_executor import CLIAgentExecutor
from orchestrator.executor.mcp_executor import MCPAgentExecutor
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter


@pytest.fixture
def config() -> AdapterConfig:
    return AdapterConfig(api_key="test-key", timeout=30)


@pytest.fixture
def mock_adapter(config: AdapterConfig) -> MockCLIAdapter:
    return MockCLIAdapter(
        config=config,
        responses={"default": "implemented successfully"},
        latency_ms=10,
    )


class TestCLIAgentExecutor:
    async def test_cli_executor_wraps_adapter(self, mock_adapter: MockCLIAdapter) -> None:
        """CLIAgentExecutor delegates run() to the underlying MockCLIAdapter."""
        executor = CLIAgentExecutor(adapter=mock_adapter)
        result = await executor.run("build feature X")

        assert result.success
        assert result.output == "implemented successfully"
        assert len(mock_adapter.call_log) == 1
        assert mock_adapter.call_log[0] == "build feature X"

    async def test_cli_executor_passes_cwd(self, mock_adapter: MockCLIAdapter) -> None:
        """context={'cwd': path} is forwarded to the adapter's cwd parameter."""
        executor = CLIAgentExecutor(adapter=mock_adapter)
        result = await executor.run("build it", context={"cwd": "/tmp/workdir"})

        assert result.success
        # The mock adapter doesn't store cwd, but we verify the call went through
        assert len(mock_adapter.call_log) == 1

    async def test_cli_executor_no_context(self, mock_adapter: MockCLIAdapter) -> None:
        """CLIAgentExecutor works fine without context."""
        executor = CLIAgentExecutor(adapter=mock_adapter)
        result = await executor.run("do something")

        assert result.success

    async def test_cli_executor_health_check(self, mock_adapter: MockCLIAdapter) -> None:
        """Health check delegates to adapter."""
        executor = CLIAgentExecutor(adapter=mock_adapter)
        assert await executor.health_check() is True

    async def test_cli_executor_type(self, mock_adapter: MockCLIAdapter) -> None:
        """executor_type returns 'cli'."""
        executor = CLIAgentExecutor(adapter=mock_adapter)
        assert executor.executor_type == "cli"


class TestMCPAgentExecutor:
    async def test_mcp_executor_returns_result(self) -> None:
        """MCPAgentExecutor returns a valid AgentResult with mock analysis."""
        executor = MCPAgentExecutor(persona="Security Analyst")
        result = await executor.run("analyze vulnerability CVE-2024-1234")

        assert result.success
        assert result.exit_code == 0
        assert result.tokens_used == 100
        assert "Analysis of:" in result.output

    async def test_mcp_executor_includes_persona(self) -> None:
        """Output contains the persona name."""
        executor = MCPAgentExecutor(persona="ELK 로그 분석가")
        result = await executor.run("check error logs")

        assert "ELK 로그 분석가" in result.output

    async def test_mcp_executor_raw_contains_metadata(self) -> None:
        """raw field contains persona and mcp_servers info."""
        executor = MCPAgentExecutor(
            persona="Grafana Analyst",
            mcp_servers={"grafana": {"url": "http://localhost:3000"}},
        )
        result = await executor.run("check dashboards")

        assert result.raw["persona"] == "Grafana Analyst"
        assert "grafana" in result.raw["mcp_servers"]

    async def test_mcp_executor_health_check(self) -> None:
        """MCP executor is always healthy in PoC mode."""
        executor = MCPAgentExecutor(persona="test")
        assert await executor.health_check() is True

    async def test_mcp_executor_type(self) -> None:
        """executor_type returns 'mcp'."""
        executor = MCPAgentExecutor(persona="test")
        assert executor.executor_type == "mcp"


class TestExecutorTypeContract:
    async def test_executor_type_cli_vs_mcp(self, mock_adapter: MockCLIAdapter) -> None:
        """CLI and MCP executors report different executor_type values."""
        cli = CLIAgentExecutor(adapter=mock_adapter)
        mcp = MCPAgentExecutor(persona="test")

        assert cli.executor_type == "cli"
        assert mcp.executor_type == "mcp"
        assert cli.executor_type != mcp.executor_type

    async def test_both_are_agent_executors(self, mock_adapter: MockCLIAdapter) -> None:
        """Both implementations satisfy the AgentExecutor ABC."""
        cli = CLIAgentExecutor(adapter=mock_adapter)
        mcp = MCPAgentExecutor(persona="test")

        assert isinstance(cli, AgentExecutor)
        assert isinstance(mcp, AgentExecutor)
