"""Add helper."""

from __future__ import annotations

from typing import overload

Number = int | float

__all__ = ["Number", "add"]

_INVALID_OPERAND_ERROR_MESSAGE = "add() arguments must be int or float"


@overload
def add(a: int, b: int) -> int: ...


@overload
def add(a: int, b: float) -> float: ...


@overload
def add(a: float, b: int) -> float: ...


@overload
def add(a: float, b: float) -> float: ...


def add(a: Number, b: Number) -> Number:
    """두 수의 합을 반환한다.

    Args:
        a: 첫 번째 숫자
        b: 두 번째 숫자

    Returns:
        두 숫자의 합. 두 인자가 모두 int이면 int, 하나라도 float이면 float.

    Raises:
        TypeError: ``a`` 또는 ``b``가 ``int`` 또는 ``float``가 아닌 경우
    """
    if _is_invalid_operand(a) or _is_invalid_operand(b):
        raise TypeError(_INVALID_OPERAND_ERROR_MESSAGE)
    return a + b


def _is_invalid_operand(value: object) -> bool:
    """지원하지 않는 피연산자인지 여부를 반환한다."""
    return isinstance(value, bool) or not isinstance(value, Number)
