"""★ PoC 전용 — Simulates an incident analysis team using MCPAgentExecutor + TaskBoard."""

from __future__ import annotations

import pytest

from orchestrator.events.bus import EventBus
from orchestrator.executor.mcp_executor import MCPAgentExecutor
from orchestrator.executor.synthesizer import Synthesizer
from orchestrator.queue.board import TaskBoard
from orchestrator.queue.models import TaskItem, TaskState


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def board(event_bus: EventBus) -> TaskBoard:
    b = TaskBoard(event_bus)
    b.add_lane("elk")
    b.add_lane("grafana")
    b.add_lane("k8s")
    return b


class TestIncidentAnalysisTeam:
    async def test_incident_analysis_team(self, board: TaskBoard) -> None:
        """Full E2E: 3 MCP agents analyze an incident in parallel, then synthesize."""
        executors = {
            "elk": MCPAgentExecutor(
                persona="ELK 로그 분석가",
                mcp_servers={"elasticsearch": {}},
            ),
            "grafana": MCPAgentExecutor(persona="Grafana 메트릭 분석가"),
            "k8s": MCPAgentExecutor(persona="K8s 클러스터 분석가"),
        }

        # Submit parallel tasks (no dependencies)
        ids: list[str] = []
        for lane in ["elk", "grafana", "k8s"]:
            task = TaskItem(title=f"Analyze {lane}", lane=lane)
            await board.submit(task)
            ids.append(task.id)

        # Each executor claims and runs its lane's task
        results = []
        for lane, executor in executors.items():
            claimed = await board.claim(lane, timeout=5)
            assert claimed is not None, f"Failed to claim task from lane '{lane}'"

            result = await executor.run(claimed.description or claimed.title)
            await board.complete(claimed.id, result.output)
            results.append(result)

        # Synthesize all results into a report
        synth = Synthesizer(strategy="narrative")
        report = await synth.synthesize(results, "서비스 장애 분석")

        # Verify all tasks completed
        for tid in ids:
            stored = board.get_task(tid)
            assert stored is not None
            assert stored.state == TaskState.DONE

        # Verify synthesized report contains all analyses
        assert "ELK" in report
        assert "Grafana" in report
        assert "K8s" in report
        assert "종합 보고서" in report
        assert "서비스 장애 분석" in report
        assert len(results) == 3

    async def test_incident_team_structured_output(self, board: TaskBoard) -> None:
        """Structured synthesis produces JSON with all agent results."""
        import json

        executors = {
            "elk": MCPAgentExecutor(persona="ELK analyst"),
            "grafana": MCPAgentExecutor(persona="Grafana analyst"),
            "k8s": MCPAgentExecutor(persona="K8s analyst"),
        }

        for lane in ["elk", "grafana", "k8s"]:
            await board.submit(TaskItem(title=f"Check {lane}", lane=lane))

        results = []
        for lane, executor in executors.items():
            claimed = await board.claim(lane, timeout=5)
            assert claimed is not None
            result = await executor.run(claimed.title)
            await board.complete(claimed.id, result.output)
            results.append(result)

        synth = Synthesizer(strategy="structured")
        report = await synth.synthesize(results, "incident triage")

        data = json.loads(report)
        assert data["agent_count"] == 3
        assert len(data["results"]) == 3

    async def test_incident_team_health_checks(self) -> None:
        """All MCP executors pass health checks."""
        executors = [
            MCPAgentExecutor(persona="ELK 로그 분석가"),
            MCPAgentExecutor(persona="Grafana 메트릭 분석가"),
            MCPAgentExecutor(persona="K8s 클러스터 분석가"),
        ]
        for executor in executors:
            assert await executor.health_check() is True
