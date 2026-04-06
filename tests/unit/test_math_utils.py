"""Unit tests for math utility helpers."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from orchestrator.math_utils import add


def test_add_returns_sum_for_integers(add_integer_operands: tuple[int, int]) -> None:
    left, right = add_integer_operands

    assert add(left, right) == 5


def test_add_returns_int_when_both_operands_are_integers() -> None:
    assert isinstance(add(2, 3), int)


def test_add_returns_sum_for_mixed_numeric_types(
    add_mixed_operands: tuple[int, float],
) -> None:
    left, right = add_mixed_operands

    assert add(left, right) == 2.5


def test_add_returns_float_type_for_mixed_numeric_types(
    add_mixed_operands: tuple[int, float],
) -> None:
    left, right = add_mixed_operands

    assert isinstance(add(left, right), float)


def test_add_returns_float_when_both_operands_are_floats(
    add_float_operands: tuple[float, float],
) -> None:
    left, right = add_float_operands

    assert add(left, right) == 4.0


def test_add_returns_float_type_when_both_operands_are_floats(
    add_float_operands: tuple[float, float],
) -> None:
    left, right = add_float_operands

    assert isinstance(add(left, right), float)


def test_add_supports_negative_numbers() -> None:
    assert add(-4, -6) == -10


def test_add_preserves_zero_identity() -> None:
    assert add(0, 7) == 7


def test_add_preserves_operand_order_for_mixed_numeric_types() -> None:
    assert add(2, 0.5) == add(0.5, 2)


def test_add_supports_large_integers(
    add_large_integer_operands: tuple[int, int],
) -> None:
    left, right = add_large_integer_operands

    assert add(left, right) == 2 * 10**18


def test_add_handles_floating_point_precision_with_approximation(
    add_precision_operands: tuple[float, float],
) -> None:
    left, right = add_precision_operands

    assert add(left, right) == pytest.approx(0.3)


def test_add_propagates_nan_inputs(add_nan_operand: float) -> None:
    assert math.isnan(add(add_nan_operand, 1.0))


def test_add_supports_infinite_operands(
    add_infinite_operands: tuple[float, float],
) -> None:
    left, right = add_infinite_operands

    assert add(left, right) == float("inf")


def test_add_returns_nan_for_opposite_infinities(
    add_opposite_infinite_operands: tuple[float, float],
) -> None:
    left, right = add_opposite_infinite_operands

    assert math.isnan(add(left, right))


def test_add_rejects_non_numeric_left_operand(
    add_invalid_string_operand: str,
) -> None:
    with pytest.raises(TypeError, match="int or float"):
        add(add_invalid_string_operand, 2)  # type: ignore[arg-type]


def test_add_rejects_non_numeric_right_operand(
    add_invalid_decimal_operand: Decimal,
) -> None:
    with pytest.raises(TypeError, match="int or float"):
        add(1, add_invalid_decimal_operand)  # type: ignore[arg-type]


def test_add_rejects_boolean_left_operand(add_invalid_bool_operand: bool) -> None:
    with pytest.raises(TypeError, match="int or float"):
        add(add_invalid_bool_operand, 2)


def test_add_rejects_boolean_right_operand() -> None:
    with pytest.raises(TypeError, match="int or float"):
        add(2, False)


def test_add_rejects_none_operand(add_invalid_none_operand: None) -> None:
    with pytest.raises(TypeError, match="int or float"):
        add(add_invalid_none_operand, 1)  # type: ignore[arg-type]


def test_add_rejects_complex_numbers(
    add_invalid_complex_operand: complex,
) -> None:
    with pytest.raises(TypeError, match="int or float"):
        add(add_invalid_complex_operand, 3)  # type: ignore[arg-type]
