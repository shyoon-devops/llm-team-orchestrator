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


def test_quality_gate_defaults():
    """Quality Gate 설정 필드가 올바른 기본값을 가진다."""
    config = OrchestratorConfig()
    assert config.quality_gate_enabled is True
    assert config.max_review_iterations == 2
    assert config.quality_gate_verdict_format == "json"


def test_execution_defaults():
    """Execution 설정 필드가 올바른 기본값을 가진다."""
    config = OrchestratorConfig()
    assert config.poll_interval == 0.5
    assert config.worktree_cleanup is True
    assert config.merge_strategy == "theirs"


def test_logging_defaults():
    """Logging 설정 필드가 올바른 기본값을 가진다."""
    config = OrchestratorConfig()
    assert config.progress_interval == 15
    assert config.show_cli_output is False


def test_quality_gate_override():
    """Quality Gate 설정을 오버라이드할 수 있다."""
    config = OrchestratorConfig(
        quality_gate_enabled=False,
        max_review_iterations=5,
        quality_gate_verdict_format="keyword",
    )
    assert config.quality_gate_enabled is False
    assert config.max_review_iterations == 5
    assert config.quality_gate_verdict_format == "keyword"


def test_execution_override():
    """Execution 설정을 오버라이드할 수 있다."""
    config = OrchestratorConfig(
        poll_interval=2.0,
        worktree_cleanup=False,
        merge_strategy="ours",
    )
    assert config.poll_interval == 2.0
    assert config.worktree_cleanup is False
    assert config.merge_strategy == "ours"
