"""전체 테스트 공통 fixture."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from decimal import Decimal

import pytest
import pytest_asyncio

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


@pytest.fixture
def add_integer_operands() -> tuple[int, int]:
    """정수 덧셈 기본 케이스."""
    return (2, 3)


@pytest.fixture
def add_mixed_operands() -> tuple[int, float]:
    """정수와 실수 혼합 덧셈 케이스."""
    return (2, 0.5)


@pytest.fixture
def add_large_integer_operands() -> tuple[int, int]:
    """큰 정수 덧셈 케이스."""
    return (10**18, 10**18)


@pytest.fixture
def add_float_operands() -> tuple[float, float]:
    """실수 덧셈 기본 케이스."""
    return (1.25, 2.75)


@pytest.fixture
def add_precision_operands() -> tuple[float, float]:
    """부동소수점 정밀도 검증 케이스."""
    return (0.1, 0.2)


@pytest.fixture
def add_nan_operand() -> float:
    """NaN 입력 케이스."""
    return float("nan")


@pytest.fixture
def add_infinite_operands() -> tuple[float, float]:
    """무한대 연산 케이스."""
    return (float("inf"), 1.0)


@pytest.fixture
def add_opposite_infinite_operands() -> tuple[float, float]:
    """부호가 반대인 무한대 연산 케이스."""
    return (float("inf"), float("-inf"))


@pytest.fixture
def add_invalid_string_operand() -> str:
    """문자열 입력 에러 케이스."""
    return "2"


@pytest.fixture
def add_invalid_bool_operand() -> bool:
    """bool 입력 에러 케이스."""
    return True


@pytest.fixture
def add_invalid_none_operand() -> None:
    """None 입력 에러 케이스."""
    return None


@pytest.fixture
def add_invalid_complex_operand() -> complex:
    """복소수 입력 에러 케이스."""
    return 1 + 2j


@pytest.fixture
def add_invalid_decimal_operand() -> Decimal:
    """Decimal 입력 에러 케이스."""
    return Decimal("1.5")


@pytest.fixture
def python_executable() -> str:
    """현재 테스트 런타임의 Python 실행 파일 경로."""
    return sys.executable


@pytest_asyncio.fixture
async def python_subprocess_runner(
    python_executable: str,
) -> Callable[[str], Awaitable[tuple[int, str, str]]]:
    """Python one-liner를 subprocess로 실행하는 헬퍼."""

    async def _run(code: str) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            python_executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode().strip(), stderr.decode().strip()

    return _run
