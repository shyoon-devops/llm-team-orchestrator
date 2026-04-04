"""Circuit breaker configuration using aiobreaker."""

from __future__ import annotations

from aiobreaker import CircuitBreaker

from orchestrator.errors.exceptions import CLIError


def create_circuit_breaker(
    fail_max: int = 3,
    timeout_duration: float = 30.0,
) -> CircuitBreaker:
    """Create a circuit breaker for CLI adapter calls."""
    return CircuitBreaker(
        fail_max=fail_max,
        timeout_duration=timeout_duration,
        exclude=[
            # Don't count parse errors as circuit failures
            # since they indicate CLI responded but output was unexpected
        ],
        expected_exception=CLIError,
    )
