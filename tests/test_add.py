"""Unit tests for src.add."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from src.add import add


def test_add_returns_sum_for_integers(add_integer_operands: tuple[int, int]) -> None:
    left, right = add_integer_operands

    assert add(left, right) == 5


def test_add_returns_int_for_integer_operands(add_integer_operands: tuple[int, int]) -> None:
    left, right = add_integer_operands

    assert isinstance(add(left, right), int)


def test_add_returns_sum_for_mixed_operands(add_mixed_operands: tuple[int, float]) -> None:
    left, right = add_mixed_operands

    assert add(left, right) == 2.5


def test_add_returns_float_for_mixed_operands(add_mixed_operands: tuple[int, float]) -> None:
    left, right = add_mixed_operands

    assert isinstance(add(left, right), float)


def test_add_returns_float_when_left_operand_is_float() -> None:
    assert isinstance(add(0.5, 2), float)


def test_add_returns_sum_for_float_operands(add_float_operands: tuple[float, float]) -> None:
    left, right = add_float_operands

    assert add(left, right) == 4.0


def test_add_returns_float_for_float_operands(add_float_operands: tuple[float, float]) -> None:
    left, right = add_float_operands

    assert isinstance(add(left, right), float)


def test_add_supports_negative_and_positive_operands() -> None:
    assert add(-1, 1) == 0


def test_add_preserves_zero_identity() -> None:
    assert add(0, 7) == 7


def test_add_is_commutative_for_mixed_operands() -> None:
    assert add(2, 0.5) == add(0.5, 2)


def test_add_supports_large_integers(add_large_integer_operands: tuple[int, int]) -> None:
    left, right = add_large_integer_operands

    assert add(left, right) == 2 * 10**18


def test_add_handles_floating_point_precision(
    add_precision_operands: tuple[float, float],
) -> None:
    left, right = add_precision_operands

    assert add(left, right) == pytest.approx(0.3)


def test_add_propagates_nan(add_nan_operand: float) -> None:
    assert math.isnan(add(add_nan_operand, 1.0))


def test_add_supports_positive_infinity(
    add_infinite_operands: tuple[float, float],
) -> None:
    left, right = add_infinite_operands

    assert add(left, right) == float("inf")


def test_add_returns_nan_for_opposite_infinities(
    add_opposite_infinite_operands: tuple[float, float],
) -> None:
    left, right = add_opposite_infinite_operands

    assert math.isnan(add(left, right))


def test_add_raises_type_error_for_string_operand(
    add_invalid_string_operand: str,
) -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(add_invalid_string_operand, 1)  # type: ignore[arg-type]


def test_add_raises_type_error_for_string_right_operand() -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(1, "2")  # type: ignore[arg-type]


def test_add_raises_type_error_for_none_operand(add_invalid_none_operand: None) -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(add_invalid_none_operand, 1)  # type: ignore[arg-type]


def test_add_raises_type_error_for_boolean_operand(add_invalid_bool_operand: bool) -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(add_invalid_bool_operand, 1)


def test_add_raises_type_error_for_boolean_right_operand() -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(1, False)


def test_add_raises_type_error_for_decimal_operand(
    add_invalid_decimal_operand: Decimal,
) -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(add_invalid_decimal_operand, 1)  # type: ignore[arg-type]


def test_add_raises_type_error_for_decimal_right_operand() -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(1, Decimal("1.5"))  # type: ignore[arg-type]


def test_add_raises_type_error_for_complex_operand(
    add_invalid_complex_operand: complex,
) -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(add_invalid_complex_operand, 1)  # type: ignore[arg-type]


def test_add_raises_type_error_for_complex_right_operand() -> None:
    with pytest.raises(TypeError, match="add\\(\\) arguments must be int or float"):
        add(1, 1 + 2j)  # type: ignore[arg-type]
