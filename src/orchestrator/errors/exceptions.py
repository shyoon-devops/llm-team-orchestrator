"""Custom exception hierarchy for the orchestrator."""


class OrchestratorError(Exception):
    """Base exception for all orchestrator errors."""


class CLIError(OrchestratorError):
    """Base exception for CLI-related errors."""


class CLIExecutionError(CLIError):
    """CLI process exited with non-zero exit code."""


class CLITimeoutError(CLIError):
    """CLI process timed out."""


class CLIParseError(CLIError):
    """Failed to parse CLI output."""


class CLINotFoundError(CLIError):
    """CLI tool is not installed."""


class AuthError(OrchestratorError):
    """Authentication-related error."""


class ContextError(OrchestratorError):
    """Context sharing error."""


class AllProvidersFailedError(OrchestratorError):
    """All provider fallbacks exhausted."""
