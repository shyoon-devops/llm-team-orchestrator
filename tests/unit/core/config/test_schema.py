"""Tests for core/config/schema.py."""

from orchestrator.core.config.schema import OrchestratorConfig


def test_default_config():
    config = OrchestratorConfig()
    assert config.app_name == "agent-team-orchestrator"
    assert config.default_timeout == 300
    assert config.default_max_retries == 3
    assert config.api_port == 8000
    assert config.cli_priority == ["claude", "codex", "gemini"]


def test_config_override():
    config = OrchestratorConfig(default_timeout=600, api_port=9000)
    assert config.default_timeout == 600
    assert config.api_port == 9000


def test_config_log_level():
    config = OrchestratorConfig(log_level="DEBUG")
    assert config.log_level == "DEBUG"
