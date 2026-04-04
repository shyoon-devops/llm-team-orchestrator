"""Unit tests for data models."""

from orchestrator.models.schemas import AdapterConfig, AgentResult, TaskConfig


class TestAdapterConfig:
    def test_defaults(self) -> None:
        config = AdapterConfig()
        assert config.api_key == ""
        assert config.timeout == 300
        assert config.max_retries == 3
        assert config.extra == {}

    def test_custom_values(self) -> None:
        config = AdapterConfig(api_key="sk-test", timeout=60, max_retries=5)
        assert config.api_key == "sk-test"
        assert config.timeout == 60
        assert config.max_retries == 5


class TestAgentResult:
    def test_success_property(self) -> None:
        result = AgentResult(output="ok", exit_code=0)
        assert result.success is True

    def test_failure_property(self) -> None:
        result = AgentResult(output="err", exit_code=1)
        assert result.success is False

    def test_defaults(self) -> None:
        result = AgentResult(output="test", exit_code=0)
        assert result.duration_ms == 0
        assert result.tokens_used == 0
        assert result.raw == {}


class TestTaskConfig:
    def test_defaults(self) -> None:
        config = TaskConfig(task="implement auth")
        assert config.planner == "claude"
        assert config.implementer == "claude"
        assert config.reviewer == "claude"
        assert config.timeout == 600

    def test_custom_roles(self) -> None:
        config = TaskConfig(
            task="refactor",
            planner="claude",
            implementer="codex",
            reviewer="gemini",
        )
        assert config.implementer == "codex"
        assert config.reviewer == "gemini"
