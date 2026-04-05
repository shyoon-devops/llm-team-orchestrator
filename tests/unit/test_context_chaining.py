"""Tests for V2-2: context chaining — _build_prompt with depends_on results."""

from __future__ import annotations

from typing import Any

from orchestrator.core.events.bus import EventBus
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.models import TaskItem
from orchestrator.core.queue.worker import AgentWorker


class StubExecutor(AgentExecutor):
    """Captures the prompt passed to run()."""

    executor_type: str = "mock"

    def __init__(self) -> None:
        self.last_prompt: str = ""

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.last_prompt = prompt
        return AgentResult(output="stub output", exit_code=0)

    async def health_check(self) -> bool:
        return True


async def test_build_prompt_without_deps() -> None:
    """depends_on이 없으면 원본 description만 반환."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    task = TaskItem(
        id="t1",
        title="Test task",
        description="Implement feature X",
        lane="implementer",
        depends_on=[],
        pipeline_id="pipe-1",
    )

    prompt = await worker._build_prompt(task)
    assert prompt == "Implement feature X"
    assert "이전 단계 결과" not in prompt


async def test_build_prompt_with_deps() -> None:
    """depends_on 태스크의 result가 프롬프트에 포함된다."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    # Submit and complete the dependency task
    dep_task = TaskItem(
        id="dep-1",
        title="Architect task",
        description="Design the architecture",
        lane="architect",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(dep_task)
    # Claim and complete
    claimed = await board.claim("architect", "worker-arch")
    assert claimed is not None
    await board.complete("dep-1", "JWT middleware design with 3 endpoints")

    # Create the dependent task
    impl_task = TaskItem(
        id="t1",
        title="Implementer task",
        description="Implement the designed features",
        lane="implementer",
        depends_on=["dep-1"],
        pipeline_id="pipe-1",
    )

    prompt = await worker._build_prompt(impl_task)
    assert "Implement the designed features" in prompt
    assert "이전 단계 결과" in prompt
    assert "[architect]" in prompt
    assert "JWT middleware design with 3 endpoints" in prompt


async def test_build_prompt_with_multiple_deps() -> None:
    """여러 depends_on 태스크의 결과가 모두 포함된다."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="reviewer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    # First dep: architect
    arch_task = TaskItem(
        id="dep-arch",
        title="Architect",
        description="Design",
        lane="architect",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(arch_task)
    claimed = await board.claim("architect", "w-arch")
    assert claimed is not None
    await board.complete("dep-arch", "Architecture document A")

    # Second dep: implementer
    impl_task = TaskItem(
        id="dep-impl",
        title="Implementer",
        description="Build",
        lane="implementer",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(impl_task)
    claimed = await board.claim("implementer", "w-impl")
    assert claimed is not None
    await board.complete("dep-impl", "Implementation code B")

    # Reviewer depends on both
    review_task = TaskItem(
        id="t-review",
        title="Review",
        description="Review the code",
        lane="reviewer",
        depends_on=["dep-arch", "dep-impl"],
        pipeline_id="pipe-1",
    )

    prompt = await worker._build_prompt(review_task)
    assert "Review the code" in prompt
    assert "[architect]" in prompt
    assert "Architecture document A" in prompt
    assert "[implementer]" in prompt
    assert "Implementation code B" in prompt


async def test_build_prompt_truncates_result() -> None:
    """선행 결과가 3000자를 초과하면 잘린다."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    long_result = "X" * 5000
    dep_task = TaskItem(
        id="dep-long",
        title="Long task",
        description="Produce long output",
        lane="architect",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(dep_task)
    claimed = await board.claim("architect", "w-arch")
    assert claimed is not None
    await board.complete("dep-long", long_result)

    task = TaskItem(
        id="t1",
        title="Next task",
        description="Process results",
        lane="implementer",
        depends_on=["dep-long"],
        pipeline_id="pipe-1",
    )

    prompt = await worker._build_prompt(task)
    # The injected result should be truncated to 3000 chars
    assert len(prompt) < len(long_result)
    assert "X" * 3000 in prompt
    assert "X" * 3001 not in prompt


async def test_build_prompt_skips_missing_dep_result() -> None:
    """depends_on 태스크가 결과 없이 있으면 건너뛴다."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    # Submit a dep but don't complete it (no result)
    dep_task = TaskItem(
        id="dep-empty",
        title="Incomplete",
        description="Pending",
        lane="architect",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(dep_task)

    task = TaskItem(
        id="t1",
        title="Task",
        description="Build features",
        lane="implementer",
        depends_on=["dep-empty"],
        pipeline_id="pipe-1",
    )

    prompt = await worker._build_prompt(task)
    # Header should still be added, but no [architect] section since result is empty
    assert "Build features" in prompt
    assert "이전 단계 결과" in prompt
    assert "[architect]" not in prompt


async def test_run_with_heartbeat_uses_enriched_prompt() -> None:
    """_run_with_heartbeat should use _build_prompt (enriched) instead of raw description."""
    board = TaskBoard()
    bus = EventBus()
    executor = StubExecutor()
    worker = AgentWorker(
        worker_id="w1",
        lane="implementer",
        board=board,
        executor=executor,
        event_bus=bus,
    )

    # Set up dependency
    dep_task = TaskItem(
        id="dep-x",
        title="Dep",
        description="Design",
        lane="architect",
        depends_on=[],
        pipeline_id="pipe-1",
    )
    await board.submit(dep_task)
    claimed = await board.claim("architect", "w-a")
    assert claimed is not None
    await board.complete("dep-x", "Design result: use React")

    # Create task with dependency
    task = TaskItem(
        id="t-impl",
        title="Implement",
        description="Implement features",
        lane="implementer",
        depends_on=["dep-x"],
        pipeline_id="pipe-1",
    )

    result = await worker._run_with_heartbeat(task)
    assert result.output == "stub output"
    # Verify the executor received the enriched prompt
    assert "이전 단계 결과" in executor.last_prompt
    assert "Design result: use React" in executor.last_prompt
