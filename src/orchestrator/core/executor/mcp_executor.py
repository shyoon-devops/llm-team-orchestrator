"""MCPAgentExecutor — MCP server-based agent executor (stub for Phase 1)."""

from __future__ import annotations

from typing import Any

import structlog

from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AgentResult

logger = structlog.get_logger()


class MCPAgentExecutor(AgentExecutor):
    """MCP 서버 기반 에이전트 실행기.

    LLM을 직접 호출하면서 MCP 서버의 도구를 사용하여 작업을 수행한다.
    Phase 1에서는 스텁으로 구현한다.

    Attributes:
        executor_type: "mcp" (고정)
        model: LLM 모델 이름
        mcp_servers: MCP 서버 정의 딕셔너리
        persona_prompt: 에이전트 페르소나 프롬프트
    """

    executor_type: str = "mcp"

    def __init__(
        self,
        model: str,
        mcp_servers: dict[str, Any] | None = None,
        persona_prompt: str = "",
    ) -> None:
        """
        Args:
            model: LiteLLM 호환 모델 이름.
            mcp_servers: MCP 서버 이름 -> MCPServerDef 매핑.
            persona_prompt: 에이전트 페르소나 프롬프트.
        """
        self.model = model
        self.mcp_servers = mcp_servers or {}
        self.persona_prompt = persona_prompt

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """LLM + MCP 도구로 작업을 수행하고 결과를 반환한다.

        Phase 1에서는 NotImplementedError를 발생시킨다.
        """
        raise NotImplementedError("MCPAgentExecutor is not yet implemented (Phase 3)")

    async def health_check(self) -> bool:
        """MCP 서버 연결 가능 여부를 확인한다.

        Phase 1에서는 False를 반환한다.
        """
        return False
