"""전체 테스트 공통 fixture."""

from __future__ import annotations

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.types import OrchestratorEvent
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.models import TaskItem, TaskState


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    """테스트용 OrchestratorConfig (환경변수 불필요)."""
    return OrchestratorConfig(
        default_timeout=10,
        default_max_retries=2,
        log_level="DEBUG",
        cli_priority=["claude", "codex", "gemini"],
        worktree_base_dir="/tmp/test-worktrees",
        api_host="127.0.0.1",
        api_port=8888,
        preset_dirs=["tests/mocks/fixtures"],
    )


@pytest.fixture
def event_bus() -> EventBus:
    """테스트용 EventBus 인스턴스."""
    return EventBus()


@pytest.fixture
def captured_events(event_bus: EventBus) -> list[OrchestratorEvent]:
    """이벤트 버스에서 발행된 이벤트를 캡처하는 리스트."""
    events: list[OrchestratorEvent] = []

    async def _capture(event: OrchestratorEvent) -> None:
        events.append(event)

    event_bus.subscribe(_capture)
    return events


@pytest.fixture
def task_board() -> TaskBoard:
    """테스트용 TaskBoard 인스턴스."""
    return TaskBoard(max_retries=3)


@pytest.fixture
def sample_task_item() -> TaskItem:
    """테스트용 TaskItem 인스턴스."""
    return TaskItem(
        id="task-001",
        title="JWT 미들웨어 구현",
        lane="implementer",
        state=TaskState.TODO,
        depends_on=[],
        assigned_to=None,
        result="",
        retry_count=0,
        max_retries=3,
        pipeline_id="pipe-001",
    )


@pytest.fixture
def sample_task_items() -> list[TaskItem]:
    """3개의 테스트용 TaskItem (의존 관계 포함)."""
    return [
        TaskItem(
            id="task-001",
            title="인증 모듈 설계",
            lane="architect",
            state=TaskState.TODO,
            depends_on=[],
            pipeline_id="pipe-001",
        ),
        TaskItem(
            id="task-002",
            title="인증 모듈 구현",
            lane="implementer",
            state=TaskState.BACKLOG,
            depends_on=["task-001"],
            pipeline_id="pipe-001",
        ),
        TaskItem(
            id="task-003",
            title="코드 리뷰",
            lane="reviewer",
            state=TaskState.BACKLOG,
            depends_on=["task-002"],
            pipeline_id="pipe-001",
        ),
    ]
