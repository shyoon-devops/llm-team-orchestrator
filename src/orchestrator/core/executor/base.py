"""AgentExecutor ABC — domain-agnostic agent execution interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from orchestrator.core.models.schemas import AgentResult


class AgentExecutor(ABC):
    """도메인 무관 에이전트 실행 인터페이스.

    모든 에이전트 실행기(CLI, MCP, Mock)는 이 ABC를 상속한다.
    run()으로 프롬프트를 실행하고, health_check()로 가용성을 확인한다.

    Attributes:
        executor_type: 실행기 유형 식별자. "cli" | "mcp" | "mock"
    """

    executor_type: str  # 서브클래스에서 클래스 변수로 정의

    @abstractmethod
    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """프롬프트를 에이전트에 전달하고 결과를 반환한다.

        Args:
            prompt: 에이전트에 전달할 프롬프트 문자열.
            timeout: 최대 실행 시간 (초). 초과 시 TimeoutError.
            context: 추가 컨텍스트 (이전 결과, 파일 목록 등).

        Returns:
            AgentResult: 실행 결과.

        Raises:
            CLIExecutionError: 프로세스 실행 실패.
            CLITimeoutError: 타임아웃 초과.
            CLIParseError: 출력 파싱 실패.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """에이전트 가용성을 확인한다.

        Returns:
            bool: 가용하면 True, 아니면 False.
        """
        ...
