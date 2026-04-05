"""Tests for core/errors/exceptions.py."""

from orchestrator.core.errors.exceptions import (
    AllProvidersFailedError,
    CLIExecutionError,
    CLINotFoundError,
    CLITimeoutError,
    DecompositionError,
    OrchestratorError,
    PresetNotFoundError,
    TaskNotFoundError,
)


def test_orchestrator_error_base():
    err = OrchestratorError("test error")
    assert err.message == "test error"
    assert err.error_code == "ORCHESTRATOR_ERROR"
    assert err.http_status == 500
    assert not err.retryable
    assert err.details == {}


def test_cli_execution_error_retryable():
    err = CLIExecutionError("failed", cli="claude", exit_code=1)
    assert err.retryable is True
    assert err.cli == "claude"


def test_cli_execution_error_oom_not_retryable():
    err = CLIExecutionError("oom", cli="claude", exit_code=137)
    assert err.retryable is False


def test_cli_timeout_error():
    err = CLITimeoutError("timed out", cli="gemini", timeout_seconds=300)
    assert err.timeout_seconds == 300
    assert err.http_status == 504
    assert err.retryable is True


def test_cli_not_found_error():
    err = CLINotFoundError("not found", cli="codex")
    assert err.retryable is False
    assert err.http_status == 503


def test_task_not_found_error():
    err = TaskNotFoundError(task_id="task-123")
    assert err.task_id == "task-123"
    assert err.http_status == 404


def test_preset_not_found_error():
    err = PresetNotFoundError(preset_name="unknown", preset_type="team")
    assert err.preset_name == "unknown"
    assert err.preset_type == "team"


def test_decomposition_error():
    err = DecompositionError("failed", task="build thing", reason="llm_error")
    assert err.task == "build thing"
    assert err.retryable is True


def test_all_providers_failed():
    attempted = [
        {"cli": "claude", "error_code": "CLI_TIMEOUT", "message": "timed out"},
        {"cli": "codex", "error_code": "CLI_EXECUTION_ERROR", "message": "exit 1"},
    ]
    err = AllProvidersFailedError(task_id="task-001", attempted=attempted)
    assert err.http_status == 502
    assert not err.retryable
    assert err.task_id == "task-001"
    assert len(err.attempted) == 2
    assert "claude" in str(err)
