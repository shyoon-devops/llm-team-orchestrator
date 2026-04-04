"""Retry decorator configuration using tenacity."""

from __future__ import annotations

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from orchestrator.errors.exceptions import CLIError, CLITimeoutError


def _before_sleep_log(retry_state: RetryCallState) -> None:
    import structlog

    log = structlog.get_logger()
    log.warning(
        "retrying_cli_call",
        attempt=retry_state.attempt_number,
        exception=str(retry_state.outcome.exception()) if retry_state.outcome else None,
    )


cli_retry = retry(
    retry=retry_if_exception_type((CLIError, CLITimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=_before_sleep_log,
    reraise=True,
)
