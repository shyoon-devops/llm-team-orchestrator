"""Unit tests for CLI adapters using mock adapters."""

import pytest

from orchestrator.errors.exceptions import CLIExecutionError, CLITimeoutError
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import FailingMockAdapter, MockCLIAdapter


@pytest.fixture
def config() -> AdapterConfig:
    return AdapterConfig(api_key="test-key")


@pytest.fixture
def mock_adapter(config: AdapterConfig) -> MockCLIAdapter:
    return MockCLIAdapter(
        config=config,
        responses={"default": "test output"},
        latency_ms=10,
    )


class TestMockCLIAdapter:
    async def test_run_returns_result(self, mock_adapter: MockCLIAdapter) -> None:
        result = await mock_adapter.run("hello")
        assert result.output == "test output"
        assert result.exit_code == 0
        assert result.success is True

    async def test_call_log(self, mock_adapter: MockCLIAdapter) -> None:
        await mock_adapter.run("first")
        await mock_adapter.run("second")
        assert mock_adapter.call_log == ["first", "second"]

    async def test_health_check(self, mock_adapter: MockCLIAdapter) -> None:
        assert await mock_adapter.health_check() is True

    async def test_provider_name(self, mock_adapter: MockCLIAdapter) -> None:
        assert mock_adapter.provider_name == "mock"

    async def test_timeout_failure(self, config: AdapterConfig) -> None:
        adapter = MockCLIAdapter(config=config, fail_on={"timeout"}, latency_ms=10)
        with pytest.raises(CLITimeoutError):
            await adapter.run("trigger timeout")

    async def test_error_failure(self, config: AdapterConfig) -> None:
        adapter = MockCLIAdapter(config=config, fail_on={"error"}, latency_ms=10)
        with pytest.raises(CLIExecutionError):
            await adapter.run("trigger error")


class TestFailingMockAdapter:
    async def test_always_fails(self, config: AdapterConfig) -> None:
        adapter = FailingMockAdapter(config=config, error_message="boom")
        with pytest.raises(CLIExecutionError, match="boom"):
            await adapter.run("anything")

    async def test_health_check_false(self, config: AdapterConfig) -> None:
        adapter = FailingMockAdapter(config=config)
        assert await adapter.health_check() is False
