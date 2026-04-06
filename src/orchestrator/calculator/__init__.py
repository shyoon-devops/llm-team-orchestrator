"""Calculator library — 확장 가능한 계산기 패키지.

Public API:
    - Calculator: 메인 Facade 클래스 (계산, 이력, 연산 등록)
    - Operation: 연산 Protocol (커스텀 연산 구현 시 참조)
    - CalculationResult: 계산 결과 모델
    - CalculatorError / DivisionByZeroError / InvalidOperationError / OperandError: 예외 계층

Usage:
    >>> from orchestrator.calculator import Calculator
    >>> calc = Calculator()
    >>> calc.add(3, 5)
    8.0
"""

from orchestrator.calculator.errors import (
    CalculatorError,
    DivisionByZeroError,
    InvalidOperationError,
    OperandError,
)
from orchestrator.calculator.interfaces import Operation
from orchestrator.calculator.models import CalculationResult

__all__ = [
    # Facade
    "Calculator",
    # Interface
    "Operation",
    # Models
    "CalculationResult",
    # Errors
    "CalculatorError",
    "DivisionByZeroError",
    "InvalidOperationError",
    "OperandError",
]


def __getattr__(name: str) -> type:
    """Lazy import for Calculator to avoid circular imports."""
    if name == "Calculator":
        from orchestrator.calculator.calculator import Calculator

        return Calculator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
