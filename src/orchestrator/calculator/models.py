"""Calculator domain models.

계산 결과를 표현하는 Pydantic 모델을 정의한다.
프로젝트 전체 컨벤션(Pydantic v2)을 따른다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CalculationResult(BaseModel):
    """단일 계산의 결과를 나타내는 불변(immutable) 모델.

    Attributes:
        operation: 수행된 연산 이름 (예: "add", "div").
        operand_a: 첫 번째 피연산자.
        operand_b: 두 번째 피연산자.
        result: 연산 결과값.
        timestamp: 연산 수행 시각 (UTC).

    Example:
        >>> entry = CalculationResult(
        ...     operation="add", operand_a=3.0, operand_b=5.0, result=8.0
        ... )
        >>> entry.model_dump()
        {'operation': 'add', 'operand_a': 3.0, 'operand_b': 5.0, 'result': 8.0, 'timestamp': ...}
    """

    model_config = {"frozen": True}

    operation: str = Field(description="수행된 연산 식별자")
    operand_a: float = Field(description="첫 번째 피연산자")
    operand_b: float = Field(description="두 번째 피연산자")
    result: float = Field(description="연산 결과값")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="연산 수행 시각 (UTC)",
    )
