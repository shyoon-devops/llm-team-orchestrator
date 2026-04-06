"""CLIAgentExecutor — CLI subprocess-based agent executor."""

from __future__ import annotations

from typing import Any

import structlog

from orchestrator.core.adapters.base import CLIAdapter, OutputCallback
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AdapterConfig, AgentResult

logger = structlog.get_logger()


class CLIAgentExecutor(AgentExecutor):
    """CLI subprocess 기반 에이전트 실행기.

    내부적으로 CLIAdapter를 사용하여 CLI 프로세스를 실행한다.
    persona 프롬프트를 자동으로 주입하고, 결과를 파싱하여 AgentResult를 반환한다.

    Attributes:
        executor_type: "cli" (고정)
        adapter: CLIAdapter 인스턴스 (Claude/Codex/Gemini)
        config: AdapterConfig 실행 설정
        persona_prompt: 시스템 프롬프트에 주입할 페르소나 텍스트
    """

    executor_type: str = "cli"

    def __init__(
        self,
        adapter: CLIAdapter,
        config: AdapterConfig,
        persona_prompt: str = "",
    ) -> None:
        """
        Args:
            adapter: CLIAdapter 구현체 (ClaudeAdapter, CodexAdapter, GeminiAdapter).
            config: 어댑터 실행 설정.
            persona_prompt: 에이전트 페르소나 프롬프트. 프롬프트 앞에 결합됨.
        """
        self.adapter = adapter
        self.config = config
        self.persona_prompt = persona_prompt
        self._on_output: OutputCallback | None = None

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """CLI subprocess를 실행하여 결과를 반환한다.

        1. persona_prompt + prompt를 결합
        2. context가 있으면 프롬프트에 추가 정보 삽입
        3. adapter.run()으로 CLI 실행
        4. 결과를 AgentResult로 파싱하여 반환
        """
        full_prompt = prompt
        if context:
            context_text = "\n".join(f"- {k}: {v}" for k, v in context.items())
            full_prompt = f"컨텍스트:\n{context_text}\n\n{prompt}"

        run_config = self.config.model_copy(update={"timeout": timeout})

        return await self.adapter.run(
            full_prompt,
            run_config,
            system_prompt=self.persona_prompt or None,
            on_output=self._on_output,
        )

    async def health_check(self) -> bool:
        """CLI 바이너리 존재 여부 및 인증 상태를 확인한다."""
        return await self.adapter.health_check()
