"""Tests for core/models/schemas.py."""

from orchestrator.core.models.schemas import AdapterConfig, AgentResult


def test_agent_result_defaults():
    result = AgentResult(output="hello")
    assert result.output == "hello"
    assert result.exit_code == 0
    assert result.duration_ms == 0
    assert result.tokens_used == 0
    assert result.raw == {}


def test_agent_result_with_values():
    result = AgentResult(
        output="done", exit_code=1, duration_ms=500, tokens_used=100, raw={"k": "v"}
    )
    assert result.exit_code == 1
    assert result.duration_ms == 500
    assert result.raw == {"k": "v"}


def test_adapter_config_defaults():
    config = AdapterConfig()
    assert config.api_key is None
    assert config.timeout == 300
    assert config.model is None
    assert config.extra_args == []
    assert config.env == {}
    assert config.working_dir is None


def test_adapter_config_with_api_key():
    config = AdapterConfig(api_key="secret-key")
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "secret-key"
