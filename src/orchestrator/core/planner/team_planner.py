"""TeamPlanner — LLM-based task decomposition and team planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from orchestrator.core.models.pipeline import SubTask
from orchestrator.core.presets.models import (
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)
from orchestrator.core.utils import generate_id

if TYPE_CHECKING:
    from orchestrator.core.presets.registry import PresetRegistry

logger = structlog.get_logger()


class TeamPlanner:
    """LLM 기반 태스크 분해기.

    사용자 태스크를 서브태스크 + 팀 구성으로 분해한다.
    team_preset이 주어지면 프리셋에 따라 서브태스크를 생성하고,
    주어지지 않으면 기본 팀을 자동 구성한다 (LLM 자동 구성은 향후 구현).

    Attributes:
        model: 분해에 사용할 LLM 모델 이름.
        preset_registry: 프리셋 레지스트리 참조.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        preset_registry: PresetRegistry | None = None,
    ) -> None:
        """TeamPlanner를 초기화한다.

        Args:
            model: 분해에 사용할 LLM 모델. 기본값 "claude-sonnet-4-20250514".
            preset_registry: 프리셋 레지스트리. 자동 팀 구성 시 사용 가능한 프리셋을 참조.
        """
        self.model = model
        self.preset_registry = preset_registry

    async def plan_team(
        self,
        task: str,
        *,
        team_preset: TeamPreset | None = None,
        target_repo: str | None = None,
    ) -> tuple[list[SubTask], TeamPreset]:
        """사용자 태스크를 서브태스크로 분해하고, 팀을 구성한다.

        Args:
            task: 사용자 태스크 설명.
            team_preset: 사전 정의된 팀 프리셋. None이면 기본 팀을 자동 구성.
            target_repo: 대상 리포지토리 경로. 코드 분석 컨텍스트 제공.

        Returns:
            (서브태스크 목록, 사용된/생성된 팀 프리셋).

        Raises:
            ValueError: task가 빈 문자열인 경우.
        """
        if not task.strip():
            msg = "Task description cannot be empty"
            raise ValueError(msg)

        if team_preset is not None:
            return self._plan_from_preset(task, team_preset)

        return self._plan_auto(task, target_repo=target_repo)

    def _plan_from_preset(
        self,
        task: str,
        team_preset: TeamPreset,
    ) -> tuple[list[SubTask], TeamPreset]:
        """프리셋 기반으로 서브태스크를 생성한다.

        Args:
            task: 사용자 태스크 설명.
            team_preset: 팀 프리셋.

        Returns:
            (서브태스크 목록, 사용된 팀 프리셋).
        """
        # task name -> SubTask ID 매핑
        task_name_to_id: dict[str, str] = {}
        for task_name in team_preset.tasks:
            task_name_to_id[task_name] = generate_id("sub")

        subtasks: list[SubTask] = []
        for task_name, task_def in team_preset.tasks.items():
            # Resolve assigned_cli from agent preset if available
            assigned_cli = self._resolve_cli(team_preset, task_def.agent)

            # Map depends_on from task names to SubTask IDs
            depends_on_ids = [
                task_name_to_id[dep] for dep in task_def.depends_on if dep in task_name_to_id
            ]

            subtask = SubTask(
                id=task_name_to_id[task_name],
                description=task_def.description,
                assigned_preset=task_def.agent,
                assigned_cli=assigned_cli,
                depends_on=depends_on_ids,
            )
            subtasks.append(subtask)

        logger.info(
            "plan_from_preset",
            team_preset=team_preset.name,
            subtask_count=len(subtasks),
            task=task[:100],
        )
        return subtasks, team_preset

    def _plan_auto(
        self,
        task: str,
        *,
        target_repo: str | None = None,
    ) -> tuple[list[SubTask], TeamPreset]:
        """자동으로 기본 팀을 구성한다.

        향후 LLM 기반 자동 분해를 구현할 예정.
        현재는 단일 implementer 에이전트로 구성된 기본 팀을 반환한다.

        Args:
            task: 사용자 태스크 설명.
            target_repo: 대상 리포지토리 경로.

        Returns:
            (서브태스크 목록, 생성된 기본 팀 프리셋).
        """
        default_preset = TeamPreset(
            name="auto-generated",
            description=f"자동 생성된 팀: {task[:80]}",
            agents={
                "implementer": TeamAgentDef(preset="implementer"),
            },
            tasks={
                "main": TeamTaskDef(
                    description=task,
                    agent="implementer",
                    depends_on=[],
                ),
            },
            workflow="sequential",
            synthesis_strategy="narrative",
        )

        subtask_id = generate_id("sub")
        subtasks = [
            SubTask(
                id=subtask_id,
                description=task,
                assigned_preset="implementer",
                assigned_cli="codex",
            ),
        ]

        logger.info(
            "plan_auto",
            subtask_count=1,
            task=task[:100],
            target_repo=target_repo,
        )
        return subtasks, default_preset

    def _resolve_cli(
        self,
        team_preset: TeamPreset,
        agent_name: str,
    ) -> str | None:
        """에이전트 이름으로 할당할 CLI를 결정한다.

        Args:
            team_preset: 팀 프리셋.
            agent_name: 에이전트 이름 (팀 프리셋의 agents 키).

        Returns:
            CLI 이름 또는 None.
        """
        agent_def = team_preset.agents.get(agent_name)
        if agent_def is None:
            return None

        # Try to resolve from preset_registry
        if self.preset_registry is not None:
            try:
                if agent_def.overrides:
                    merged = self.preset_registry.merge_preset_with_overrides(
                        agent_def.preset, agent_def.overrides
                    )
                    return merged.preferred_cli
                agent_preset = self.preset_registry.load_agent_preset(agent_def.preset)
                return agent_preset.preferred_cli
            except KeyError:
                logger.debug(
                    "agent_preset_not_found_for_cli",
                    preset=agent_def.preset,
                )

        return None
