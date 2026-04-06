"""Calculator operation interface definitions.

이 모듈은 계산기 연산의 계약(contract)을 Protocol로 정의한다.
새로운 연산을 추가하려면 이 Protocol을 만족하는 클래스를 구현하면 된다.
명시적 상속 없이 구조적 서브타이핑(structural subtyping)으로 호환된다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Operation(Protocol):
    """단일 이항 연산을 나타내는 Protocol.

    Attributes:
        name: 연산 식별자 (예: "add", "sub", "mul"). Registry 키로 사용된다.

    Example:
        class MaxOperation:
            name = "max"
            def execute(self, a: float, b: float) -> float:
                return max(a, b)

        assert isinstance(MaxOperation(), Operation)  # True (structural)
    """

    @property
    def name(self) -> str:
        """연산의 고유 식별자."""
        ...

    def execute(self, a: float, b: float) -> float:
        """두 피연산자에 대해 연산을 수행한다.

        Args:
            a: 첫 번째 피연산자.
            b: 두 번째 피연산자.

        Returns:
            연산 결과값.

        Raises:
            CalculatorError: 연산 수행이 불가능한 경우
                (예: 0으로 나누기, 오버플로 등).
        """
        ...
