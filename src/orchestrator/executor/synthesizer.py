"""★ PoC 전용 — Synthesizer aggregates multiple agent results into a report."""

from __future__ import annotations

import json

from orchestrator.models.schemas import AgentResult


class Synthesizer:
    """Aggregates partial results from multiple agents into a coherent output.

    Strategies:
    - "narrative": combine into prose summary (default)
    - "structured": merge into structured JSON
    - "checklist": format as checklist of findings
    """

    def __init__(self, strategy: str = "narrative") -> None:
        self.strategy = strategy

    async def synthesize(self, results: list[AgentResult], task: str) -> str:
        """Combine multiple results into a final report.

        For PoC: concatenates results with headers.
        For production: would call LLM to synthesize.

        Args:
            results: List of AgentResult from multiple agents.
            task: High-level task description for the report title.
        """
        if self.strategy == "structured":
            return self._structured(results, task)
        if self.strategy == "checklist":
            return self._checklist(results, task)
        return self._narrative(results, task)

    def _narrative(self, results: list[AgentResult], task: str) -> str:
        sections = [f"# 종합 보고서: {task}\n"]
        for i, r in enumerate(results, 1):
            sections.append(f"## Agent {i} 분석 결과\n{r.output}\n")
        sections.append(f"---\n총 {len(results)}개 에이전트 분석 완료.")
        return "\n".join(sections)

    def _structured(self, results: list[AgentResult], task: str) -> str:
        data = {
            "task": task,
            "agent_count": len(results),
            "results": [{"output": r.output, "tokens": r.tokens_used} for r in results],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _checklist(self, results: list[AgentResult], task: str) -> str:
        lines = [f"# Checklist: {task}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"- [x] Agent {i}: {r.output[:100]}")
        return "\n".join(lines)
