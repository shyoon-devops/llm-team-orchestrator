"""TeamPlanner — LLM-based task decomposition and team planning."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

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

    use_llm=True일 때 프리셋 기반에서도 LLM을 호출하여 역할별 세부 지시를 생성한다.

    Attributes:
        model: 분해에 사용할 LLM 모델 이름.
        preset_registry: 프리셋 레지스트리 참조.
        use_llm: LLM 기반 역할별 세부 지시 생성 여부.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        preset_registry: PresetRegistry | None = None,
        *,
        use_llm: bool = False,
    ) -> None:
        """TeamPlanner를 초기화한다.

        Args:
            model: 분해에 사용할 LLM 모델. 기본값 "claude-sonnet-4-20250514".
            preset_registry: 프리셋 레지스트리. 자동 팀 구성 시 사용 가능한 프리셋을 참조.
            use_llm: LLM 기반 역할별 세부 지시 생성 활성화.
        """
        self.model = model
        self.preset_registry = preset_registry
        self.use_llm = use_llm

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
            if self.use_llm:
                return await self._plan_from_preset_with_llm(task, team_preset)
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

            # 프리셋 설명 + 사용자 원본 태스크를 합쳐서 CLI에 전달
            full_description = (
                f"{task_def.description.strip()}\n\n"
                f"사용자 태스크: {task}"
            )

            subtask = SubTask(
                id=task_name_to_id[task_name],
                description=full_description,
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

    async def _plan_from_preset_with_llm(
        self,
        task: str,
        team_preset: TeamPreset,
    ) -> tuple[list[SubTask], TeamPreset]:
        """LLM을 호출하여 프리셋의 각 역할에 맞는 세부 지시를 생성한다.

        Args:
            task: 사용자 태스크 설명.
            team_preset: 팀 프리셋.

        Returns:
            (서브태스크 목록, 사용된 팀 프리셋).
        """
        import asyncio

        # 역할 정보 구성
        roles_info: list[dict[str, str]] = []
        for task_name, task_def in team_preset.tasks.items():
            roles_info.append({
                "role": task_name,
                "agent": task_def.agent,
                "base_description": task_def.description.strip()[:100],
            })

        prompt = (
            "다음 태스크를 팀 역할에 맞게 분해하세요.\n\n"
            f"태스크: {task}\n\n"
            f"역할 목록:\n"
        )
        for info in roles_info:
            prompt += f"- {info['role']} ({info['agent']}): {info['base_description']}\n"

        prompt += (
            "\n각 역할에 대해 구체적인 지시를 JSON 배열로 작성하세요. "
            "반드시 아래 형식만 출력하세요:\n"
            "```json\n"
            "[\n"
            '  {"role": "역할이름", "instruction": "구체적인 지시사항..."}\n'
            "]\n"
            "```\n"
            "instruction은 해당 역할이 이 태스크에서 수행해야 할 구체적인 작업을 상세히 기술하세요."
        )

        try:
            # CLI subprocess로 호출 (API 키 불필요, CLI 인증 사용)
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                "--output-format", "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"CLI failed: {stderr.decode()[:200]}")
            raw = stdout.decode()
            instructions = self._parse_llm_instructions(raw, team_preset)
        except Exception:
            logger.warning(
                "planner_llm_fallback",
                reason="LLM call failed, falling back to preset-based planning",
            )
            return self._plan_from_preset(task, team_preset)

        # SubTask 생성
        task_name_to_id: dict[str, str] = {}
        for task_name in team_preset.tasks:
            task_name_to_id[task_name] = generate_id("sub")

        subtasks: list[SubTask] = []
        for task_name, task_def in team_preset.tasks.items():
            assigned_cli = self._resolve_cli(team_preset, task_def.agent)
            depends_on_ids = [
                task_name_to_id[dep] for dep in task_def.depends_on if dep in task_name_to_id
            ]

            # LLM이 생성한 세부 지시 사용, 없으면 프리셋 description 폴백
            llm_instruction = instructions.get(task_name)
            if llm_instruction:
                full_description = (
                    f"{llm_instruction}\n\n"
                    f"사용자 태스크: {task}"
                )
            else:
                full_description = (
                    f"{task_def.description.strip()}\n\n"
                    f"사용자 태스크: {task}"
                )

            subtask = SubTask(
                id=task_name_to_id[task_name],
                description=full_description,
                assigned_preset=task_def.agent,
                assigned_cli=assigned_cli,
                depends_on=depends_on_ids,
            )
            subtasks.append(subtask)

        logger.info(
            "plan_from_preset_with_llm",
            team_preset=team_preset.name,
            subtask_count=len(subtasks),
            llm_roles=list(instructions.keys()),
            task=task[:100],
        )
        return subtasks, team_preset

    def _parse_llm_instructions(
        self,
        raw: str,
        team_preset: TeamPreset,
    ) -> dict[str, str]:
        """LLM 응답에서 역할별 지시를 파싱한다.

        Args:
            raw: LLM 응답 텍스트.
            team_preset: 팀 프리셋 (역할 이름 검증용).

        Returns:
            {역할이름: 세부지시} 딕셔너리.
        """
        # JSON 코드블록 추출
        import re
        json_match = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
        json_str = json_match.group(1).strip() if json_match else raw.strip()

        try:
            items: list[dict[str, Any]] = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("planner_llm_parse_failed", raw=raw[:200])
            return {}

        valid_roles = set(team_preset.tasks.keys())
        result: dict[str, str] = {}
        for item in items:
            role = item.get("role", "")
            instruction = item.get("instruction", "")
            if role in valid_roles and instruction:
                result[role] = instruction

        return result

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
