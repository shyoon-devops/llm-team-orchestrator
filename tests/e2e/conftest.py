"""E2E 테스트 전용 fixture.

MockAgentExecutor를 사용하여 실제 CLI 호출 없이
전체 파이프라인 흐름을 검증한다.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, ClassVar

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.types import OrchestratorEvent
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.pipeline import PipelineStatus
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.presets.models import (
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)

# ── Mock Executors ──────────────────────────────────────────────────


class MockAgentExecutor(AgentExecutor):
    """E2E 테스트용 mock agent executor.

    실제 CLI 호출 없이 사실적인 코드 결과를 반환한다.
    """

    executor_type: str = "mock"

    def __init__(
        self,
        *,
        output: str = "Mock output",
        fail: bool = False,
        delay: float = 0.0,
    ) -> None:
        self.output = output
        self.fail = fail
        self.delay = delay
        self.cli_name: str = "mock"
        self.run_count = 0

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.run_count += 1
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.fail:
            msg = "MockAgentExecutor forced failure"
            raise RuntimeError(msg)
        return AgentResult(
            output=f"{self.output}: {prompt[:80]}",
            exit_code=0,
            duration_ms=150,
            tokens_used=75,
        )

    async def health_check(self) -> bool:
        return True


class RealisticCodeExecutor(AgentExecutor):
    """사실적인 코드 출력을 반환하는 mock executor.

    에이전트 역할에 따라 다른 결과를 반환한다.
    """

    executor_type: str = "mock"

    ROLE_OUTPUTS: ClassVar[dict[str, str]] = {
        "architect": (
            "## 아키텍처 설계 완료\n\n"
            "### JWT 인증 미들웨어 아키텍처\n"
            "1. `src/middleware/auth.py` — JWT 검증 미들웨어\n"
            "2. `src/auth/jwt_handler.py` — 토큰 생성/검증 유틸\n"
            "3. `src/auth/models.py` — 인증 관련 Pydantic 모델\n\n"
            "### 인터페이스 정의\n"
            "```python\n"
            "class JWTMiddleware:\n"
            "    async def __call__(self, request, call_next): ...\n"
            "```\n"
        ),
        "implementer": (
            "## 구현 완료\n\n"
            "### 생성된 파일\n"
            "- `src/middleware/auth.py` (120 lines)\n"
            "- `src/auth/jwt_handler.py` (85 lines)\n"
            "- `src/auth/models.py` (45 lines)\n\n"
            "### 핵심 구현\n"
            "```python\n"
            "import jwt\n"
            "from fastapi import Request, HTTPException\n\n"
            "class JWTMiddleware:\n"
            "    def __init__(self, secret_key: str):\n"
            "        self.secret_key = secret_key\n\n"
            "    async def __call__(self, request: Request, call_next):\n"
            "        token = request.headers.get('Authorization')\n"
            "        if not token:\n"
            "            raise HTTPException(status_code=401)\n"
            "        payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])\n"
            "        request.state.user = payload\n"
            "        return await call_next(request)\n"
            "```\n"
        ),
        "reviewer": (
            "## 코드 리뷰 완료\n\n"
            "### 리뷰 결과: APPROVED (minor issues)\n\n"
            "#### 긍정적 사항\n"
            "- 클린 아키텍처 원칙 준수\n"
            "- 에러 핸들링 적절\n"
            "- 타입 힌트 완전\n\n"
            "#### 개선 제안\n"
            "1. `jwt.decode()`에 `options` 파라미터로 만료 검증 추가 필요\n"
            "2. 로깅 추가 권장\n"
            "3. Rate limiting 고려 필요\n"
        ),
        "tester": (
            "## 테스트 작성 완료\n\n"
            "### 테스트 파일\n"
            "- `tests/test_jwt_middleware.py` (15 tests)\n"
            "- `tests/test_jwt_handler.py` (8 tests)\n\n"
            "### 테스트 커버리지: 94%\n"
            "```\n"
            "Name                        Stmts   Miss  Cover\n"
            "-----------------------------------------------\n"
            "src/middleware/auth.py         45      2    96%\n"
            "src/auth/jwt_handler.py        32      3    91%\n"
            "src/auth/models.py             18      1    94%\n"
            "-----------------------------------------------\n"
            "TOTAL                          95      6    94%\n"
            "```\n"
        ),
        "elk": (
            "## ELK 로그 분석 결과\n\n"
            "### 에러 패턴 분석 (최근 30분)\n"
            "- HTTP 500 에러: 247건 (api-gateway → user-service)\n"
            "- Connection Refused: 89건 (user-service → postgres)\n"
            "- Timeout: 23건 (api-gateway, p99=12.3s)\n\n"
            "### 타임라인\n"
            "- 14:32 UTC: postgres connection pool 포화 시작\n"
            "- 14:35 UTC: user-service 500 에러 급증\n"
            "- 14:38 UTC: api-gateway cascade failure\n\n"
            "### 근본 원인 추정\n"
            "PostgreSQL connection pool 고갈로 인한 cascade failure\n"
        ),
        "default": "작업이 완료되었습니다.",
    }

    def __init__(self, *, delay: float = 0.05) -> None:
        self.cli_name: str = "mock"
        self.delay = delay
        self.execution_log: list[str] = []

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # prompt에서 역할 키워드를 추출하여 적절한 출력 선택
        role = "default"
        prompt_lower = prompt.lower()
        for key in self.ROLE_OUTPUTS:
            if key in prompt_lower:
                role = key
                break

        self.execution_log.append(prompt[:100])
        output = self.ROLE_OUTPUTS.get(role, self.ROLE_OUTPUTS["default"])
        return AgentResult(
            output=f"{output}\n\n(입력 태스크: {prompt[:80]})",
            exit_code=0,
            duration_ms=200,
            tokens_used=100,
        )

    async def health_check(self) -> bool:
        return True


class FailingMockExecutor(AgentExecutor):
    """항상 실패하는 mock executor (fallback 테스트용)."""

    executor_type: str = "mock"

    def __init__(self, *, error_msg: str = "Simulated CLI timeout") -> None:
        self.cli_name: str = "mock-fail"
        self.error_msg = error_msg
        self.run_count = 0

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.run_count += 1
        raise RuntimeError(self.error_msg)

    async def health_check(self) -> bool:
        return False


class PartialFailExecutor(AgentExecutor):
    """일부만 실패하는 mock executor.

    fail_on_prompts에 포함된 키워드가 prompt에 있으면 실패한다.
    """

    executor_type: str = "mock"

    def __init__(
        self,
        *,
        fail_keywords: list[str] | None = None,
    ) -> None:
        self.cli_name: str = "mock-partial"
        self.fail_keywords = fail_keywords or []
        self.run_count = 0

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.run_count += 1
        prompt_lower = prompt.lower()
        for keyword in self.fail_keywords:
            if keyword.lower() in prompt_lower:
                msg = f"Simulated failure for keyword: {keyword}"
                raise RuntimeError(msg)

        return AgentResult(
            output=f"Success: {prompt[:80]}",
            exit_code=0,
            duration_ms=100,
            tokens_used=50,
        )

    async def health_check(self) -> bool:
        return True


# ── Helper ──────────────────────────────────────────────────────────


def _patch_executor(engine: OrchestratorEngine, executor: AgentExecutor) -> None:
    """Engine의 _create_executor_for_preset을 mock으로 교체한다."""
    engine._create_executor_for_preset = lambda *_args, **_kwargs: executor  # type: ignore[assignment]


async def wait_for_pipeline(
    engine: OrchestratorEngine,
    task_id: str,
    *,
    max_wait: float = 10.0,
    poll_interval: float = 0.1,
) -> None:
    """파이프라인이 터미널 상태에 도달할 때까지 대기한다."""
    terminal = {
        PipelineStatus.COMPLETED,
        PipelineStatus.PARTIAL_FAILURE,
        PipelineStatus.FAILED,
        PipelineStatus.CANCELLED,
    }
    elapsed = 0.0
    while elapsed < max_wait:
        current = await engine.get_pipeline(task_id)
        if current and current.status in terminal:
            return
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    msg = f"Pipeline {task_id} did not reach terminal state within {max_wait}s"
    raise TimeoutError(msg)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def e2e_sandbox_dir() -> str:
    """E2E 테스트용 임시 디렉토리 (sandbox rule)."""
    return tempfile.mkdtemp()


@pytest.fixture
def e2e_config(tmp_path: Path) -> OrchestratorConfig:
    """E2E 테스트용 OrchestratorConfig."""
    return OrchestratorConfig(
        default_timeout=10,
        default_max_retries=2,
        log_level="DEBUG",
        cli_priority=["claude", "codex", "gemini"],
        worktree_base_dir=str(tmp_path / "worktrees"),
        api_host="127.0.0.1",
        api_port=8888,
        preset_dirs=["tests/mocks/fixtures"],
        checkpoint_enabled=True,
        checkpoint_db_path=str(tmp_path / "checkpoints.sqlite"),
    )


@pytest.fixture
def e2e_engine(e2e_config: OrchestratorConfig) -> OrchestratorEngine:
    """E2E 테스트용 OrchestratorEngine (mock executor 사용)."""
    return OrchestratorEngine(config=e2e_config)


@pytest.fixture
def feature_team_preset() -> TeamPreset:
    """feature-team 프리셋 (architect -> implementer -> reviewer+tester)."""
    return TeamPreset(
        name="feature-team",
        description="기능 구현 팀: 설계 → 구현 → 리뷰 → 테스트",
        agents={
            "architect": TeamAgentDef(preset="architect"),
            "implementer": TeamAgentDef(preset="implementer"),
            "reviewer": TeamAgentDef(preset="reviewer"),
            "tester": TeamAgentDef(preset="tester"),
        },
        tasks={
            "design": TeamTaskDef(
                description="아키텍처 설계 및 인터페이스 정의",
                agent="architect",
                depends_on=[],
            ),
            "implement": TeamTaskDef(
                description="설계에 따른 코드 구현",
                agent="implementer",
                depends_on=["design"],
            ),
            "review": TeamTaskDef(
                description="구현 코드 리뷰",
                agent="reviewer",
                depends_on=["implement"],
            ),
            "test": TeamTaskDef(
                description="단위 테스트 및 통합 테스트 작성",
                agent="tester",
                depends_on=["implement"],
            ),
        },
        workflow="dag",
        synthesis_strategy="narrative",
    )


@pytest.fixture
def incident_team_preset() -> TeamPreset:
    """incident-analysis-team 프리셋 (3개 MCP 에이전트 병렬)."""
    return TeamPreset(
        name="incident-analysis-team",
        description="프로덕션 인시던트 분석 팀 — ELK/Grafana/K8s 병렬 분석",
        agents={
            "elk": TeamAgentDef(preset="elk-analyst"),
            "grafana": TeamAgentDef(preset="elk-analyst"),
            "k8s": TeamAgentDef(preset="elk-analyst"),
        },
        tasks={
            "elk-analysis": TeamTaskDef(
                description="ELK에서 에러 로그를 분석한다. 에러 패턴, 빈도, 타임라인 파악.",
                agent="elk",
                depends_on=[],
            ),
            "grafana-analysis": TeamTaskDef(
                description="Grafana 메트릭을 분석한다. CPU, 메모리, 네트워크 이상 패턴.",
                agent="grafana",
                depends_on=[],
            ),
            "k8s-analysis": TeamTaskDef(
                description="K8s 클러스터 상태를 분석한다. Pod 상태, 이벤트, 리소스 사용.",
                agent="k8s",
                depends_on=[],
            ),
        },
        workflow="parallel",
        synthesis_strategy="structured",
    )


@pytest.fixture
def captured_events(e2e_engine: OrchestratorEngine) -> list[OrchestratorEvent]:
    """이벤트 버스에서 발행된 이벤트를 캡처하는 리스트."""
    events: list[OrchestratorEvent] = []

    async def _capture(event: OrchestratorEvent) -> None:
        events.append(event)

    e2e_engine.subscribe(_capture)
    return events
