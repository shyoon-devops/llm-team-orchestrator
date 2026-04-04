"""Unit tests for exception hierarchy and error handling."""

import pytest

from orchestrator.errors.exceptions import (
    AllProvidersFailedError,
    AuthError,
    CLIError,
    CLIExecutionError,
    CLINotFoundError,
    CLIParseError,
    CLITimeoutError,
    ContextError,
    OrchestratorError,
)


class TestExceptionHierarchy:
    def test_cli_errors_are_orchestrator_errors(self) -> None:
        assert issubclass(CLIError, OrchestratorError)
        assert issubclass(CLIExecutionError, CLIError)
        assert issubclass(CLITimeoutError, CLIError)
        assert issubclass(CLIParseError, CLIError)
        assert issubclass(CLINotFoundError, CLIError)

    def test_auth_error_is_orchestrator_error(self) -> None:
        assert issubclass(AuthError, OrchestratorError)

    def test_context_error_is_orchestrator_error(self) -> None:
        assert issubclass(ContextError, OrchestratorError)

    def test_all_providers_failed_is_orchestrator_error(self) -> None:
        assert issubclass(AllProvidersFailedError, OrchestratorError)

    def test_catch_cli_error_catches_subtypes(self) -> None:
        with pytest.raises(CLIError):
            raise CLIExecutionError("failed")

    def test_catch_orchestrator_catches_all(self) -> None:
        for exc_cls in [CLIExecutionError, CLITimeoutError, AuthError, ContextError]:
            with pytest.raises(OrchestratorError):
                raise exc_cls("test")

    def test_error_messages(self) -> None:
        err = CLITimeoutError("timed out after 300s")
        assert "300s" in str(err)
