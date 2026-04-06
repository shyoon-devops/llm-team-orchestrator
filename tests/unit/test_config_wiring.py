"""Config 필드 연동 테스트 — engine/worker에서 설정이 실제로 반영되는지 검증."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.quality_gate import QualityGate, QualityVerdict


class TestOrchestratorConfigFields:
    """OrchestratorConfig 필드 존재 및 기본값 테스트."""

    def test_quality_gate_enabled_default(self) -> None:
        config = OrchestratorConfig()
        assert config.quality_gate_enabled is True

    def test_quality_gate_verdict_format_default(self) -> None:
        config = OrchestratorConfig()
        assert config.quality_gate_verdict_format == "json"

    def test_worktree_cleanup_default(self) -> None:
        config = OrchestratorConfig()
        assert config.worktree_cleanup is True

    def test_show_cli_output_default(self) -> None:
        config = OrchestratorConfig()
        assert config.show_cli_output is False

    def test_auto_merge_default(self) -> None:
        config = OrchestratorConfig()
        assert config.auto_merge is True

    def test_planner_use_llm_default(self) -> None:
        config = OrchestratorConfig()
        assert config.planner_use_llm is True


class TestQualityGateVerdictFormat:
    """QualityGate verdict_format 테스트."""

    def test_json_mode_parses_json(self) -> None:
        gate = QualityGate(verdict_format="json")
        result = '{"verdict": "approve", "feedback": "LGTM"}\nrest of review'
        verdict = gate.evaluate(result)
        assert verdict.approved is True

    def test_json_mode_falls_back_to_keyword(self) -> None:
        gate = QualityGate(verdict_format="json")
        result = "이 코드는 수정 필요합니다. XYZ를 고쳐야 합니다."
        verdict = gate.evaluate(result)
        assert verdict.approved is False

    def test_keyword_mode_ignores_json(self) -> None:
        """keyword 모드에서는 JSON verdict를 무시하고 키워드만 검사."""
        gate = QualityGate(verdict_format="keyword")
        # JSON으로는 approve이지만 키워드로는 reject
        result = '{"verdict": "approve"}\n수정 필요합니다.'
        verdict = gate.evaluate(result)
        assert verdict.approved is False

    def test_keyword_mode_approve(self) -> None:
        gate = QualityGate(verdict_format="keyword")
        result = "코드가 잘 작성되었습니다. 좋습니다."
        verdict = gate.evaluate(result)
        assert verdict.approved is True

    def test_keyword_mode_reject(self) -> None:
        gate = QualityGate(verdict_format="keyword")
        result = "이 부분은 reject합니다."
        verdict = gate.evaluate(result)
        assert verdict.approved is False

    def test_json_mode_reject(self) -> None:
        gate = QualityGate(verdict_format="json")
        result = '{"verdict": "reject", "feedback": "fix bugs"}'
        verdict = gate.evaluate(result)
        assert verdict.approved is False
        assert verdict.feedback == "fix bugs"

    def test_empty_result_approved(self) -> None:
        gate = QualityGate(verdict_format="json")
        verdict = gate.evaluate("")
        assert verdict.approved is True

    def test_default_verdict_format_is_json(self) -> None:
        gate = QualityGate()
        assert gate._verdict_format == "json"


class TestWorkerShowOutput:
    """AgentWorker show_output 플래그 테스트."""

    def test_worker_default_show_output_false(self) -> None:
        from orchestrator.core.queue.worker import AgentWorker

        worker = AgentWorker(
            worker_id="test",
            lane="test",
            board=MagicMock(),
            executor=MagicMock(),
            event_bus=MagicMock(),
        )
        assert worker._show_output is False

    def test_worker_show_output_true(self) -> None:
        from orchestrator.core.queue.worker import AgentWorker

        worker = AgentWorker(
            worker_id="test",
            lane="test",
            board=MagicMock(),
            executor=MagicMock(),
            event_bus=MagicMock(),
            show_output=True,
        )
        assert worker._show_output is True


class TestCLIProgressTable:
    """CLI progress 테이블 생성 테스트."""

    def test_build_progress_table_empty(self) -> None:
        from orchestrator.cli import _build_progress_table

        table = _build_progress_table("pipe-123", "test task", {}, 0)
        assert table.title is not None
        assert "pipe-123" in table.title

    def test_build_progress_table_with_data(self) -> None:
        from orchestrator.cli import _build_progress_table

        board_state = {
            "lanes": {
                "architect": {
                    "done": [{"title": "설계", "started_at": "2026-01-01T00:00:00", "completed_at": "2026-01-01T00:02:00"}],
                    "in_progress": [],
                },
                "implementer": {
                    "in_progress": [{"title": "구현", "started_at": "2026-01-01T00:02:00", "completed_at": None}],
                    "done": [],
                },
            }
        }
        table = _build_progress_table("pipe-123", "test task", board_state, 120)
        assert table.row_count == 2

    def test_build_progress_table_no_lanes(self) -> None:
        from orchestrator.cli import _build_progress_table

        table = _build_progress_table("pipe-123", "test task", {"lanes": {}}, 30)
        assert table.row_count == 0


class TestCLIConfigShow:
    """CLI config show 명령 테스트."""

    def test_config_show_runs(self) -> None:
        """config show 명령이 에러 없이 실행되는지 확인."""
        from typer.testing import CliRunner

        from orchestrator.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "quality_gate_enabled" in result.output
        assert "auto_merge" in result.output
