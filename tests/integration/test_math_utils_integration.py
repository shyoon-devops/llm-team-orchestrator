"""Integration tests for math utility helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_can_be_imported_and_executed_in_a_subprocess(
    python_subprocess_runner: Callable[[str], Awaitable[tuple[int, str, str]]],
) -> None:
    returncode, stdout, stderr = await python_subprocess_runner(
        "from orchestrator.math_utils import add; print(add(20, 22))",
    )

    assert returncode == 0, stderr
    assert stdout == "42"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_preserves_integer_return_type_in_a_subprocess(
    python_subprocess_runner: Callable[[str], Awaitable[tuple[int, str, str]]],
) -> None:
    returncode, stdout, stderr = await python_subprocess_runner(
        "from orchestrator.math_utils import add; print(type(add(20, 22)).__name__)",
    )

    assert returncode == 0, stderr
    assert stdout == "int"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_rejects_boolean_operands_in_a_subprocess(
    python_subprocess_runner: Callable[[str], Awaitable[tuple[int, str, str]]],
) -> None:
    returncode, _, stderr = await python_subprocess_runner(
        "from orchestrator.math_utils import add; add(True, 1)",
    )

    assert returncode != 0
    assert "TypeError: add() arguments must be int or float" in stderr


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_supports_float_precision_in_a_subprocess(
    python_subprocess_runner: Callable[[str], Awaitable[tuple[int, str, str]]],
) -> None:
    returncode, stdout, stderr = await python_subprocess_runner(
        (
            "from orchestrator.math_utils import add; "
            "result = add(0.1, 0.2); "
            "print(round(result, 10))"
        )
    )

    assert returncode == 0, stderr
    assert stdout == "0.3"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_rejects_decimal_operands_in_a_subprocess(
    python_subprocess_runner: Callable[[str], Awaitable[tuple[int, str, str]]],
) -> None:
    returncode, _, stderr = await python_subprocess_runner(
        (
            "from decimal import Decimal; "
            "from orchestrator.math_utils import add; "
            "add(Decimal('1.5'), 1)"
        )
    )

    assert returncode != 0
    assert "TypeError: add() arguments must be int or float" in stderr


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_returns_type_error_for_none_in_a_subprocess(
    python_subprocess_runner: Callable[[str], Awaitable[tuple[int, str, str]]],
) -> None:
    returncode, _, stderr = await python_subprocess_runner(
        "from orchestrator.math_utils import add; add(None, 1)",
    )

    assert returncode != 0
    assert "TypeError: add() arguments must be int or float" in stderr
