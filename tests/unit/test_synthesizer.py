"""Unit tests for Synthesizer."""

from __future__ import annotations

import json

from orchestrator.executor.synthesizer import Synthesizer
from orchestrator.models.schemas import AgentResult


def _make_result(output: str, tokens: int = 50) -> AgentResult:
    return AgentResult(
        output=output,
        exit_code=0,
        duration_ms=100,
        tokens_used=tokens,
    )


class TestNarrativeSynthesis:
    async def test_narrative_synthesis(self) -> None:
        """Narrative strategy combines results into a prose report."""
        results = [
            _make_result("ELK: found 42 error logs"),
            _make_result("Grafana: CPU spike at 14:00"),
        ]
        synth = Synthesizer(strategy="narrative")
        report = await synth.synthesize(results, "서비스 장애 분석")

        assert "종합 보고서: 서비스 장애 분석" in report
        assert "Agent 1 분석 결과" in report
        assert "Agent 2 분석 결과" in report
        assert "ELK: found 42 error logs" in report
        assert "Grafana: CPU spike at 14:00" in report
        assert "총 2개 에이전트 분석 완료" in report

    async def test_narrative_is_default(self) -> None:
        """Synthesizer defaults to narrative strategy."""
        synth = Synthesizer()
        assert synth.strategy == "narrative"

        results = [_make_result("test output")]
        report = await synth.synthesize(results, "test task")
        assert "종합 보고서" in report


class TestStructuredSynthesis:
    async def test_structured_synthesis(self) -> None:
        """Structured strategy produces valid JSON."""
        results = [
            _make_result("finding A", tokens=100),
            _make_result("finding B", tokens=200),
        ]
        synth = Synthesizer(strategy="structured")
        report = await synth.synthesize(results, "incident review")

        data = json.loads(report)
        assert data["task"] == "incident review"
        assert data["agent_count"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["output"] == "finding A"
        assert data["results"][0]["tokens"] == 100
        assert data["results"][1]["tokens"] == 200


class TestChecklistSynthesis:
    async def test_checklist_synthesis(self) -> None:
        """Checklist strategy produces markdown checklist."""
        results = [
            _make_result("security scan passed"),
            _make_result("lint check passed"),
        ]
        synth = Synthesizer(strategy="checklist")
        report = await synth.synthesize(results, "CI checks")

        assert "# Checklist: CI checks" in report
        assert "- [x] Agent 1:" in report
        assert "- [x] Agent 2:" in report
        assert "security scan passed" in report


class TestEdgeCases:
    async def test_empty_results(self) -> None:
        """Synthesizer handles empty result list gracefully."""
        synth = Synthesizer(strategy="narrative")
        report = await synth.synthesize([], "empty task")

        assert "종합 보고서: empty task" in report
        assert "총 0개 에이전트 분석 완료" in report

    async def test_unknown_strategy_falls_back_to_narrative(self) -> None:
        """Unknown strategy defaults to narrative."""
        synth = Synthesizer(strategy="unknown")
        results = [_make_result("data")]
        report = await synth.synthesize(results, "test")

        assert "종합 보고서" in report
