"""Tests for core/context/checkpoint.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.core.context.checkpoint import CheckpointStore
from orchestrator.core.models.pipeline import Pipeline, PipelineStatus, SubTask


@pytest.fixture
def checkpoint_store(tmp_path: Path) -> CheckpointStore:
    """테스트용 CheckpointStore (임시 디렉토리)."""
    db_path = str(tmp_path / "test_checkpoints.sqlite")
    return CheckpointStore(db_path=db_path)


@pytest.fixture
def sample_pipeline() -> Pipeline:
    """테스트용 Pipeline."""
    return Pipeline(
        task_id="pipeline-test-001",
        task="JWT 인증 미들웨어 구현",
        status=PipelineStatus.RUNNING,
        team_preset="feature-team",
        target_repo="/home/user/project",
        subtasks=[
            SubTask(
                id="sub-001",
                description="JWT 토큰 생성 모듈",
                assigned_preset="implementer",
                assigned_cli="claude",
            ),
            SubTask(
                id="sub-002",
                description="미들웨어 통합",
                assigned_preset="implementer",
                depends_on=["sub-001"],
            ),
        ],
    )


def test_checkpoint_save_load(
    checkpoint_store: CheckpointStore,
    sample_pipeline: Pipeline,
) -> None:
    """저장한 체크포인트를 정상적으로 복원할 수 있다."""
    checkpoint_store.save("pipeline-test-001", sample_pipeline)
    restored = checkpoint_store.load("pipeline-test-001")

    assert restored is not None
    assert restored.task_id == "pipeline-test-001"
    assert restored.task == "JWT 인증 미들웨어 구현"
    assert restored.status == PipelineStatus.RUNNING
    assert restored.team_preset == "feature-team"
    assert len(restored.subtasks) == 2
    assert restored.subtasks[0].id == "sub-001"
    assert restored.subtasks[1].depends_on == ["sub-001"]


def test_checkpoint_load_nonexistent(checkpoint_store: CheckpointStore) -> None:
    """존재하지 않는 체크포인트 로드 시 None을 반환한다."""
    result = checkpoint_store.load("nonexistent-id")
    assert result is None


def test_checkpoint_overwrite(
    checkpoint_store: CheckpointStore,
    sample_pipeline: Pipeline,
) -> None:
    """동일 ID로 저장하면 기존 체크포인트를 덮어쓴다."""
    checkpoint_store.save("pipeline-test-001", sample_pipeline)

    updated = sample_pipeline.model_copy(
        update={"status": PipelineStatus.COMPLETED, "synthesis": "종합 보고서"}
    )
    checkpoint_store.save("pipeline-test-001", updated)

    restored = checkpoint_store.load("pipeline-test-001")
    assert restored is not None
    assert restored.status == PipelineStatus.COMPLETED
    assert restored.synthesis == "종합 보고서"


def test_list_checkpoints(
    checkpoint_store: CheckpointStore,
    sample_pipeline: Pipeline,
) -> None:
    """저장된 체크포인트 목록을 반환한다."""
    assert checkpoint_store.list_checkpoints() == []

    checkpoint_store.save("pipeline-001", sample_pipeline)
    p2 = sample_pipeline.model_copy(update={"task_id": "pipeline-002"})
    checkpoint_store.save("pipeline-002", p2)

    ids = checkpoint_store.list_checkpoints()
    assert len(ids) == 2
    assert "pipeline-001" in ids
    assert "pipeline-002" in ids


def test_delete_checkpoint(
    checkpoint_store: CheckpointStore,
    sample_pipeline: Pipeline,
) -> None:
    """체크포인트를 삭제한다."""
    checkpoint_store.save("pipeline-test-001", sample_pipeline)
    assert checkpoint_store.load("pipeline-test-001") is not None

    checkpoint_store.delete("pipeline-test-001")
    assert checkpoint_store.load("pipeline-test-001") is None


def test_delete_nonexistent(checkpoint_store: CheckpointStore) -> None:
    """존재하지 않는 체크포인트 삭제는 에러 없이 무시된다."""
    checkpoint_store.delete("nonexistent")  # Should not raise


def test_checkpoint_db_directory_creation(tmp_path: Path) -> None:
    """DB 파일이 위치할 디렉토리가 없으면 자동 생성한다."""
    db_path = str(tmp_path / "deep" / "nested" / "checkpoints.sqlite")
    store = CheckpointStore(db_path=db_path)
    assert Path(db_path).parent.exists()

    pipeline = Pipeline(
        task_id="pipeline-dir-test",
        task="디렉토리 생성 테스트",
    )
    store.save("pipeline-dir-test", pipeline)
    restored = store.load("pipeline-dir-test")
    assert restored is not None


def test_checkpoint_preserves_pipeline_fields(
    checkpoint_store: CheckpointStore,
) -> None:
    """Pipeline의 모든 주요 필드가 체크포인트를 통해 보존된다."""
    from orchestrator.core.models.pipeline import WorkerResult

    pipeline = Pipeline(
        task_id="pipeline-full",
        task="전체 필드 보존 테스트",
        status=PipelineStatus.FAILED,
        team_preset="review-team",
        target_repo="/home/test/repo",
        error="All subtasks failed",
        results=[
            WorkerResult(
                subtask_id="sub-x",
                executor_type="cli",
                output="result output",
                error="execution error",
            ),
        ],
    )
    checkpoint_store.save("pipeline-full", pipeline)

    restored = checkpoint_store.load("pipeline-full")
    assert restored is not None
    assert restored.error == "All subtasks failed"
    assert len(restored.results) == 1
    assert restored.results[0].output == "result output"
    assert restored.results[0].error == "execution error"
