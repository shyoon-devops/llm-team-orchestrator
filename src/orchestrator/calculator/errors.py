"""Calculator domain exceptions.

도메인 예외 계층을 정의한다.
모든 계산기 예외는 CalculatorError를 상속하므로,
호출자는 `except CalculatorError`로 모든 계산기 에러를 일괄 처리할 수 있다.
"""

from __future__ import annotations


class CalculatorError(Exception):
    """계산기 도메인 최상위 예외.

    모든 계산기 관련 예외의 베이스 클래스.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class DivisionByZeroError(CalculatorError):
    """0으로 나누기 시도 시 발생.

    `div(x, 0)` 또는 `mod(x, 0)` 호출 시 발생한다.
    파이썬 내장 ZeroDivisionError 대신 도메인 예외를 사용하여
    호출자가 계산기 에러와 시스템 에러를 구분할 수 있게 한다.
    """

    def __init__(self, operation: str = "div") -> None:
        super().__init__(f"0으로 나눌 수 없습니다 (operation: {operation})")
        self.operation = operation


class InvalidOperationError(CalculatorError):
    """등록되지 않은 연산 이름으로 calculate() 호출 시 발생.

    Attributes:
        operation: 요청된 (미등록) 연산 이름.
        available: 현재 등록된 연산 이름 목록.
    """

    def __init__(self, operation: str, available: list[str] | None = None) -> None:
        self.operation = operation
        self.available = available or []
        hint = f" (사용 가능: {', '.join(self.available)})" if self.available else ""
        super().__init__(f"등록되지 않은 연산입니다: '{operation}'{hint}")


class OperandError(CalculatorError):
    """비정상적인 피연산자(inf, nan 등) 입력 시 발생.

    연산 수행 전 입력값을 검증하여, 무의미한 결과가
    이력에 기록되는 것을 방지한다.
    """

    def __init__(self, message: str = "유효하지 않은 피연산자입니다") -> None:
        super().__init__(message)
